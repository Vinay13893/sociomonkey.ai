"""Organisation and capability administration APIs."""

from datetime import datetime

from flask import Blueprint, jsonify, request

from app.middleware import require_auth, require_capability
from app.models.activity import ActivityLog
from app.models.base import db
from app.models.organisation import (
    BusinessRole,
    OrganisationUnit,
    OrganisationUnitMembership,
    PermissionDefinition,
    ReportingRelationship,
    RolePermission,
    UserBusinessRole,
    UserPermissionOverride,
)
from app.models.user import User
from app.services.permissions import capability_decision


organisation_bp = Blueprint('organisation', __name__, url_prefix='/api/organisation')

SCOPE_TYPES = {'OWN', 'TEAM', 'ORGANISATION_UNIT', 'PROJECT', 'TENANT', 'PLATFORM'}
EFFECTS = {'ALLOW', 'DENY'}
RELATIONSHIP_TYPES = {
    'LINE_MANAGER', 'CALLING_MANAGER', 'SALES_MANAGER', 'FUNCTIONAL_MANAGER',
    'PROJECT_MANAGER', 'LEGACY_MANAGER', 'LEGACY_ASSIGNED_MANAGER',
}


def _tenant_id():
    user = request.current_user
    tenant_id = getattr(request, 'current_tenant_id', None) or user.tenant_id
    if tenant_id is None and user.role == 'platform_owner':
        raw = request.args.get('tenant_id') or (request.get_json(silent=True) or {}).get('tenant_id')
        try:
            tenant_id = int(raw)
        except (TypeError, ValueError):
            return None
    return tenant_id


def _audit(action, resource_id=None, old_value=None, new_value=None, description=None):
    db.session.add(ActivityLog(
        tenant_id=_tenant_id(),
        user_id=request.current_user.id,
        action=action,
        module='organisation',
        resource_id=resource_id,
        resource_type='Organisation',
        old_value=old_value,
        new_value=new_value,
        description=description,
        ip_address=request.remote_addr,
    ))


def _tenant_user(user_id):
    tenant_id = _tenant_id()
    if tenant_id is None:
        return None
    return User.query.filter_by(id=user_id, tenant_id=tenant_id).first()


@organisation_bp.route('/overview', methods=['GET'])
@require_capability('organisation.view', 'TENANT')
def overview():
    tenant_id = _tenant_id()
    if tenant_id is None:
        return jsonify({'error': 'Tenant context is required'}), 400
    return jsonify({
        'counts': {
            'units': OrganisationUnit.query.filter_by(
                tenant_id=tenant_id, is_active=True
            ).count(),
            'roles': BusinessRole.query.filter(
                BusinessRole.is_active == True,  # noqa: E712
                (BusinessRole.tenant_id == tenant_id) | (BusinessRole.tenant_id.is_(None)),
            ).count(),
            'memberships': OrganisationUnitMembership.query.filter_by(
                tenant_id=tenant_id, is_active=True
            ).count(),
            'reporting_relationships': ReportingRelationship.query.filter_by(
                tenant_id=tenant_id, is_active=True
            ).count(),
        }
    }), 200


@organisation_bp.route('/units', methods=['GET'])
@require_capability('organisation.view', 'TENANT')
def list_units():
    tenant_id = _tenant_id()
    rows = OrganisationUnit.query.filter_by(tenant_id=tenant_id).order_by(
        OrganisationUnit.name.asc()
    ).all()
    return jsonify({'units': [row.to_dict() for row in rows]}), 200


@organisation_bp.route('/units', methods=['POST'])
@require_capability('organisation.configure', 'TENANT')
def create_unit():
    tenant_id = _tenant_id()
    data = request.get_json() or {}
    code = str(data.get('code') or '').strip().upper()
    name = str(data.get('name') or '').strip()
    if not code or not name:
        return jsonify({'error': 'Code and name are required'}), 400
    parent_id = data.get('parent_id')
    if parent_id and not OrganisationUnit.query.filter_by(
        id=parent_id, tenant_id=tenant_id, is_active=True
    ).first():
        return jsonify({'error': 'Parent unit not found'}), 400
    if OrganisationUnit.query.filter_by(tenant_id=tenant_id, code=code).first():
        return jsonify({'error': 'Unit code already exists'}), 409
    row = OrganisationUnit(
        tenant_id=tenant_id,
        parent_id=parent_id,
        code=code,
        name=name,
        unit_type=str(data.get('unit_type') or 'GENERAL').strip().upper(),
        description=data.get('description'),
        created_by=request.current_user.id,
    )
    db.session.add(row)
    db.session.flush()
    _audit('organisation_unit_created', row.id, new_value=row.to_dict())
    db.session.commit()
    return jsonify({'unit': row.to_dict()}), 201


@organisation_bp.route('/units/<int:unit_id>', methods=['PUT'])
@require_capability('organisation.configure', 'TENANT')
def update_unit(unit_id):
    tenant_id = _tenant_id()
    row = OrganisationUnit.query.filter_by(id=unit_id, tenant_id=tenant_id).first()
    if not row:
        return jsonify({'error': 'Organisation unit not found'}), 404
    data = request.get_json() or {}
    old = row.to_dict()
    if 'parent_id' in data:
        parent_id = data.get('parent_id')
        if parent_id == row.id:
            return jsonify({'error': 'A unit cannot be its own parent'}), 400
        if parent_id and not OrganisationUnit.query.filter_by(
            id=parent_id, tenant_id=tenant_id, is_active=True
        ).first():
            return jsonify({'error': 'Parent unit not found'}), 400
        row.parent_id = parent_id
    if 'name' in data:
        row.name = str(data['name']).strip() or row.name
    if 'unit_type' in data:
        row.unit_type = str(data['unit_type']).strip().upper()
    if 'description' in data:
        row.description = data.get('description')
    if 'is_active' in data:
        row.is_active = bool(data['is_active'])
    _audit('organisation_unit_updated', row.id, old, row.to_dict())
    db.session.commit()
    return jsonify({'unit': row.to_dict()}), 200


@organisation_bp.route('/units/<int:unit_id>/members', methods=['GET'])
@require_capability('organisation.view', 'TENANT')
def list_unit_members(unit_id):
    tenant_id = _tenant_id()
    rows = OrganisationUnitMembership.query.filter_by(
        tenant_id=tenant_id, organisation_unit_id=unit_id, is_active=True
    ).order_by(OrganisationUnitMembership.user_id.asc()).all()
    return jsonify({'memberships': [row.to_dict() for row in rows]}), 200


@organisation_bp.route('/units/<int:unit_id>/members', methods=['POST'])
@require_capability('organisation.configure', 'TENANT')
def add_unit_member(unit_id):
    tenant_id = _tenant_id()
    data = request.get_json() or {}
    user = _tenant_user(data.get('user_id'))
    unit = OrganisationUnit.query.filter_by(
        id=unit_id, tenant_id=tenant_id, is_active=True
    ).first()
    if not user or not unit:
        return jsonify({'error': 'User or organisation unit not found'}), 404
    membership_type = str(data.get('membership_type') or 'MEMBER').strip().upper()
    row = OrganisationUnitMembership.query.filter_by(
        organisation_unit_id=unit.id,
        user_id=user.id,
        membership_type=membership_type,
    ).first()
    if row:
        row.is_active = True
        row.effective_to = None
        row.is_primary = bool(data.get('is_primary', row.is_primary))
    else:
        row = OrganisationUnitMembership(
            tenant_id=tenant_id,
            organisation_unit_id=unit.id,
            user_id=user.id,
            membership_type=membership_type,
            is_primary=bool(data.get('is_primary', False)),
            created_by=request.current_user.id,
        )
        db.session.add(row)
    db.session.flush()
    _audit('organisation_membership_assigned', row.id, new_value=row.to_dict())
    db.session.commit()
    return jsonify({'membership': row.to_dict()}), 200


@organisation_bp.route('/roles', methods=['GET'])
@require_capability('organisation.view', 'TENANT')
def list_roles():
    tenant_id = _tenant_id()
    rows = BusinessRole.query.filter(
        BusinessRole.is_active == True,  # noqa: E712
        (BusinessRole.tenant_id == tenant_id) | (BusinessRole.tenant_id.is_(None)),
    ).order_by(BusinessRole.display_name.asc()).all()
    return jsonify({'roles': [row.to_dict() for row in rows]}), 200


@organisation_bp.route('/users/<int:user_id>/roles', methods=['GET'])
@require_capability('organisation.view', 'TENANT')
def list_user_roles(user_id):
    if not _tenant_user(user_id):
        return jsonify({'error': 'User not found'}), 404
    rows = UserBusinessRole.query.filter_by(user_id=user_id, is_active=True).all()
    return jsonify({'assignments': [row.to_dict() for row in rows]}), 200


@organisation_bp.route('/users/<int:user_id>/roles', methods=['POST'])
@require_capability('organisation.configure', 'TENANT')
def assign_user_role(user_id):
    tenant_id = _tenant_id()
    user = _tenant_user(user_id)
    data = request.get_json() or {}
    role = BusinessRole.query.filter(
        BusinessRole.id == data.get('business_role_id'),
        BusinessRole.is_active == True,  # noqa: E712
        (BusinessRole.tenant_id == tenant_id) | (BusinessRole.tenant_id.is_(None)),
    ).first()
    unit_id = data.get('organisation_unit_id')
    if not user or not role:
        return jsonify({'error': 'User or business role not found'}), 404
    if unit_id and not OrganisationUnit.query.filter_by(
        id=unit_id, tenant_id=tenant_id, is_active=True
    ).first():
        return jsonify({'error': 'Organisation unit not found'}), 404
    row = UserBusinessRole.query.filter_by(
        user_id=user.id,
        business_role_id=role.id,
        organisation_unit_id=unit_id,
    ).first()
    if row:
        row.is_active = True
        row.effective_to = None
        row.is_primary = bool(data.get('is_primary', row.is_primary))
    else:
        row = UserBusinessRole(
            tenant_id=tenant_id,
            user_id=user.id,
            business_role_id=role.id,
            organisation_unit_id=unit_id,
            is_primary=bool(data.get('is_primary', False)),
            assigned_by=request.current_user.id,
        )
        db.session.add(row)
    db.session.flush()
    _audit('business_role_assigned', row.id, new_value=row.to_dict())
    db.session.commit()
    return jsonify({'assignment': row.to_dict()}), 200


@organisation_bp.route('/user-role-assignments/<int:assignment_id>', methods=['DELETE'])
@require_capability('organisation.configure', 'TENANT')
def deactivate_user_role(assignment_id):
    row = UserBusinessRole.query.filter_by(
        id=assignment_id, tenant_id=_tenant_id(), is_active=True
    ).first()
    if not row:
        return jsonify({'error': 'Role assignment not found'}), 404
    row.is_active = False
    row.effective_to = datetime.utcnow()
    _audit('business_role_removed', row.id, old_value=row.to_dict())
    db.session.commit()
    return jsonify({'ok': True}), 200


@organisation_bp.route('/reporting-relationships', methods=['GET'])
@require_capability('organisation.view', 'TENANT')
def list_reporting_relationships():
    rows = ReportingRelationship.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    ).order_by(ReportingRelationship.user_id.asc()).all()
    return jsonify({'relationships': [row.to_dict() for row in rows]}), 200


@organisation_bp.route('/reporting-relationships', methods=['POST'])
@require_capability('organisation.configure', 'TENANT')
def create_reporting_relationship():
    tenant_id = _tenant_id()
    data = request.get_json() or {}
    user = _tenant_user(data.get('user_id'))
    manager = _tenant_user(data.get('manager_id'))
    relationship_type = str(
        data.get('relationship_type') or 'LINE_MANAGER'
    ).strip().upper()
    if not user or not manager:
        return jsonify({'error': 'User or manager not found'}), 404
    if user.id == manager.id:
        return jsonify({'error': 'A user cannot report to themselves'}), 400
    if relationship_type not in RELATIONSHIP_TYPES:
        return jsonify({'error': 'Invalid relationship type'}), 400
    unit_id = data.get('organisation_unit_id')
    if unit_id and not OrganisationUnit.query.filter_by(
        id=unit_id, tenant_id=tenant_id, is_active=True
    ).first():
        return jsonify({'error': 'Organisation unit not found'}), 404
    row = ReportingRelationship.query.filter_by(
        user_id=user.id,
        manager_id=manager.id,
        relationship_type=relationship_type,
        organisation_unit_id=unit_id,
    ).first()
    if row:
        row.is_active = True
        row.effective_to = None
        row.is_primary = bool(data.get('is_primary', row.is_primary))
    else:
        row = ReportingRelationship(
            tenant_id=tenant_id,
            user_id=user.id,
            manager_id=manager.id,
            relationship_type=relationship_type,
            organisation_unit_id=unit_id,
            is_primary=bool(data.get('is_primary', False)),
            created_by=request.current_user.id,
        )
        db.session.add(row)
    db.session.flush()
    _audit('reporting_relationship_created', row.id, new_value=row.to_dict())
    db.session.commit()
    return jsonify({'relationship': row.to_dict()}), 200


@organisation_bp.route('/reporting-relationships/<int:relationship_id>', methods=['DELETE'])
@require_capability('organisation.configure', 'TENANT')
def deactivate_reporting_relationship(relationship_id):
    row = ReportingRelationship.query.filter_by(
        id=relationship_id, tenant_id=_tenant_id(), is_active=True
    ).first()
    if not row:
        return jsonify({'error': 'Reporting relationship not found'}), 404
    old = row.to_dict()
    row.is_active = False
    row.effective_to = datetime.utcnow()
    _audit('reporting_relationship_removed', row.id, old_value=old)
    db.session.commit()
    return jsonify({'ok': True}), 200


@organisation_bp.route('/permissions', methods=['GET'])
@require_capability('organisation.view', 'TENANT')
def list_permissions():
    rows = PermissionDefinition.query.filter_by(is_active=True).order_by(
        PermissionDefinition.module.asc(), PermissionDefinition.action.asc()
    ).all()
    return jsonify({'permissions': [row.to_dict() for row in rows]}), 200


@organisation_bp.route('/roles/<int:role_id>/permissions', methods=['GET'])
@require_capability('organisation.view', 'TENANT')
def list_role_permissions(role_id):
    tenant_id = _tenant_id()
    role = BusinessRole.query.filter(
        BusinessRole.id == role_id,
        (BusinessRole.tenant_id == tenant_id) | (BusinessRole.tenant_id.is_(None)),
    ).first()
    if not role:
        return jsonify({'error': 'Business role not found'}), 404
    rows = RolePermission.query.filter_by(business_role_id=role.id).all()
    return jsonify({'grants': [row.to_dict() for row in rows]}), 200


@organisation_bp.route('/roles/<int:role_id>/permissions', methods=['POST'])
@require_capability('permissions.manage', 'TENANT')
def upsert_role_permission(role_id):
    tenant_id = _tenant_id()
    data = request.get_json() or {}
    role = BusinessRole.query.filter_by(id=role_id, tenant_id=tenant_id).first()
    permission = PermissionDefinition.query.filter_by(
        key=data.get('permission_key'), is_active=True
    ).first()
    scope_type = str(data.get('scope_type') or 'OWN').strip().upper()
    effect = str(data.get('effect') or 'ALLOW').strip().upper()
    if not role or not permission:
        return jsonify({'error': 'Role or permission not found'}), 404
    if scope_type not in SCOPE_TYPES or effect not in EFFECTS:
        return jsonify({'error': 'Invalid scope or effect'}), 400
    scope_ref_id = str(data.get('scope_ref_id') or '').strip() or None
    row = RolePermission.query.filter_by(
        business_role_id=role.id,
        permission_id=permission.id,
        scope_type=scope_type,
        scope_ref_id=scope_ref_id,
    ).first()
    if row:
        row.effect = effect
    else:
        row = RolePermission(
            tenant_id=tenant_id,
            business_role_id=role.id,
            permission_id=permission.id,
            scope_type=scope_type,
            scope_ref_id=scope_ref_id,
            effect=effect,
            created_by=request.current_user.id,
        )
        db.session.add(row)
    db.session.flush()
    _audit('role_permission_updated', row.id, new_value=row.to_dict())
    db.session.commit()
    return jsonify({'grant': row.to_dict()}), 200


@organisation_bp.route('/users/<int:user_id>/permission-overrides', methods=['POST'])
@require_capability('permissions.manage', 'TENANT')
def upsert_user_permission_override(user_id):
    tenant_id = _tenant_id()
    user = _tenant_user(user_id)
    data = request.get_json() or {}
    permission = PermissionDefinition.query.filter_by(
        key=data.get('permission_key'), is_active=True
    ).first()
    scope_type = str(data.get('scope_type') or 'OWN').strip().upper()
    effect = str(data.get('effect') or '').strip().upper()
    if not user or not permission:
        return jsonify({'error': 'User or permission not found'}), 404
    if scope_type not in SCOPE_TYPES or effect not in EFFECTS:
        return jsonify({'error': 'Invalid scope or effect'}), 400
    scope_ref_id = str(data.get('scope_ref_id') or '').strip() or None
    row = UserPermissionOverride.query.filter_by(
        user_id=user.id,
        permission_id=permission.id,
        scope_type=scope_type,
        scope_ref_id=scope_ref_id,
    ).first()
    if row:
        row.effect = effect
        row.reason = data.get('reason')
        row.is_active = True
        row.effective_to = None
    else:
        row = UserPermissionOverride(
            tenant_id=tenant_id,
            user_id=user.id,
            permission_id=permission.id,
            scope_type=scope_type,
            scope_ref_id=scope_ref_id,
            effect=effect,
            reason=data.get('reason'),
            created_by=request.current_user.id,
        )
        db.session.add(row)
    db.session.flush()
    _audit('user_permission_override_updated', row.id, new_value=row.to_dict())
    db.session.commit()
    return jsonify({'override': row.to_dict()}), 200


@organisation_bp.route('/permissions/check', methods=['GET'])
@require_auth
def check_permission():
    capability = str(request.args.get('capability') or '').strip()
    scope = str(request.args.get('scope') or 'OWN').strip().upper()
    if not capability or scope not in SCOPE_TYPES:
        return jsonify({'error': 'Valid capability and scope are required'}), 400
    return jsonify({
        'capability': capability,
        'decision': capability_decision(
            request.current_user,
            capability,
            scope,
            request.args.get('scope_ref_id'),
        ),
    }), 200
