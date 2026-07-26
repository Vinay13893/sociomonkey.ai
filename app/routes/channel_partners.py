"""Channel Partner profile, relationship, assignment, and timeline APIs."""

from datetime import datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload

from app.middleware import require_capability
from app.models.activity import ActivityLog
from app.models.base import db
from app.models.channel_partner import (
    ChannelPartner,
    ChannelPartnerAssignment,
    ChannelPartnerContact,
    ChannelPartnerNote,
    ChannelPartnerProject,
)
from app.models.organisation import BusinessRole, UserBusinessRole
from app.models.project import Project
from app.models.push import NotificationEvent
from app.models.user import User
from app.models.visit import Visit, VisitParticipant
from app.services.channel_partner_events import (
    notify_channel_partner_assignment,
    notify_channel_partner_profile_change,
)
from app.services.permissions import has_capability
from app.utils.time_utils import to_ist_str


channel_partners_bp = Blueprint(
    'channel_partners', __name__, url_prefix='/api/channel-partners'
)

PARTNER_TYPES = {'INDIVIDUAL', 'ORGANISATION'}
PROJECT_RELATIONSHIPS = {'PREFERRED', 'ACTIVE', 'HISTORICAL'}
ASSIGNMENT_TYPES = {
    'SALES_MANAGER', 'RELATIONSHIP_MANAGER', 'SECONDARY_RM',
}
ASSIGNMENT_ROLE_KEYS = {
    'SALES_MANAGER': {'SALES_MANAGER'},
    'RELATIONSHIP_MANAGER': {'RELATIONSHIP_MANAGER'},
    'SECONDARY_RM': {'RELATIONSHIP_MANAGER'},
}
PROFILE_FIELDS = {
    'name', 'organisation_name', 'gst_number', 'pan_number', 'rera_number',
    'address_line_1', 'address_line_2', 'city', 'state', 'country',
    'postal_code', 'tags', 'notes', 'profile_metadata',
}
IMPORTANT_PROFILE_FIELDS = {
    'name', 'organisation_name', 'gst_number', 'pan_number', 'rera_number',
}


def _tenant_id():
    return request.current_user.tenant_id or getattr(
        request, 'current_tenant_id', None
    )


def _cid():
    return str(request.headers.get('X-Correlation-ID') or uuid4())


def _can_reveal():
    return has_capability(
        request.current_user, 'channel_partners.reveal_sensitive', 'TENANT'
    )


def _audit(action, resource_type, resource_id, old, new, correlation_id):
    db.session.add(ActivityLog(
        tenant_id=_tenant_id(),
        user_id=request.current_user.id,
        action=action,
        module='channel_partners',
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=old,
        new_value=new,
        correlation_id=correlation_id,
        ip_address=request.remote_addr,
    ))


def _page_args():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 25, type=int)))
    return page, per_page


def _visible_assignment_user_ids(user):
    """None means unrestricted (admin-like); otherwise the set of user ids
    whose active assignments make a Channel Partner visible to *user* - the
    caller themself plus, for a manager, their reporting-line team (mirrors
    the Lead co-ownership visibility model in app.utils.leads)."""
    if user.role in ('superadmin', 'platform_owner'):
        return None
    from app.utils.leads import _reporting_team_ids
    return _reporting_team_ids(user)


def _can_view_partner(partner, user):
    visible_ids = _visible_assignment_user_ids(user)
    if visible_ids is None:
        return True
    return ChannelPartnerAssignment.query.filter(
        ChannelPartnerAssignment.tenant_id == _tenant_id(),
        ChannelPartnerAssignment.channel_partner_id == partner.id,
        ChannelPartnerAssignment.is_active.is_(True),
        ChannelPartnerAssignment.user_id.in_(visible_ids),
    ).first() is not None


def _partner(partner_id, include_inactive=True):
    query = ChannelPartner.query.options(
        selectinload(ChannelPartner.contacts),
        selectinload(ChannelPartner.project_associations).joinedload(
            ChannelPartnerProject.project
        ),
        selectinload(ChannelPartner.assignments).joinedload(
            ChannelPartnerAssignment.user
        ),
    ).filter_by(id=partner_id, tenant_id=_tenant_id())
    if not include_inactive:
        query = query.filter_by(is_active=True)
    return query.first()


def _normalise_strings(values, maximum=10):
    if values in (None, ''):
        return []
    if not isinstance(values, list):
        raise ValueError('Contact values must be arrays')
    result = []
    seen = set()
    for value in values:
        cleaned = str(value or '').strip()
        identity = cleaned.lower()
        if cleaned and identity not in seen:
            result.append(cleaned[:250])
            seen.add(identity)
        if len(result) >= maximum:
            break
    return result


def _normalise_tags(values):
    return _normalise_strings(values, maximum=25)


def _active_user(user_id):
    if user_id in (None, ''):
        return None
    row = User.query.filter_by(
        id=int(user_id), tenant_id=_tenant_id(), is_active=True
    ).first()
    if not row:
        raise ValueError('Active user was not found in this tenant')
    return row


def _project(project_id):
    if project_id in (None, ''):
        return None
    row = Project.query.filter_by(
        id=int(project_id), tenant_id=_tenant_id(), is_active=True
    ).first()
    if not row:
        raise ValueError('Active project was not found in this tenant')
    return row


def _role_keys_for_user(user_id):
    now = datetime.utcnow()
    rows = UserBusinessRole.query.join(
        BusinessRole,
        BusinessRole.id == UserBusinessRole.business_role_id,
    ).filter(
        UserBusinessRole.tenant_id == _tenant_id(),
        UserBusinessRole.user_id == user_id,
        UserBusinessRole.is_active.is_(True),
        UserBusinessRole.effective_from <= now,
        or_(
            UserBusinessRole.effective_to.is_(None),
            UserBusinessRole.effective_to > now,
        ),
        BusinessRole.is_active.is_(True),
    ).all()
    return {row.business_role.key for row in rows if row.business_role}


def _validate_assignment_user(user_id, assignment_type):
    user = _active_user(user_id)
    required = ASSIGNMENT_ROLE_KEYS[assignment_type]
    if not (_role_keys_for_user(user.id) & required):
        expected = ' or '.join(sorted(required)).replace('_', ' ').title()
        raise ValueError(f'Assigned user must hold the {expected} business role')
    return user


def _apply_profile(row, data):
    if 'partner_type' in data:
        partner_type = str(data.get('partner_type') or '').upper()
        if partner_type not in PARTNER_TYPES:
            raise ValueError('Invalid Channel Partner type')
        row.partner_type = partner_type
    for field in PROFILE_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if field == 'tags':
            value = _normalise_tags(value)
        elif field == 'profile_metadata':
            if value is not None and not isinstance(value, dict):
                raise ValueError('Profile metadata must be an object')
            value = value or {}
        elif field not in {'notes'} and value is not None:
            value = str(value).strip() or None
        setattr(row, field, value)
    if not str(row.name or '').strip():
        raise ValueError('Channel Partner name is required')
    if row.partner_type == 'ORGANISATION' and not row.organisation_name:
        row.organisation_name = row.name


def _contact(partner_id, contact_id):
    return ChannelPartnerContact.query.filter_by(
        id=contact_id,
        tenant_id=_tenant_id(),
        channel_partner_id=partner_id,
    ).first()


def _contact_payload(row, data):
    if 'name' in data:
        row.name = str(data.get('name') or '').strip()
    if not row.name:
        raise ValueError('Contact name is required')
    if 'designation' in data:
        row.designation = str(data.get('designation') or '').strip() or None
    if 'mobile_numbers' in data:
        row.mobile_numbers = _normalise_strings(data['mobile_numbers'])
    if 'email_addresses' in data:
        row.email_addresses = _normalise_strings(data['email_addresses'])
    if 'contact_metadata' in data:
        if data['contact_metadata'] is not None and not isinstance(
            data['contact_metadata'], dict
        ):
            raise ValueError('Contact metadata must be an object')
        row.contact_metadata = data['contact_metadata'] or {}
    if 'is_primary' in data:
        row.is_primary = bool(data['is_primary'])
    if not row.mobile_numbers and not row.email_addresses:
        raise ValueError('At least one mobile number or email address is required')


def _demote_other_primary_contacts(partner_id, except_id=None):
    query = ChannelPartnerContact.query.filter_by(
        tenant_id=_tenant_id(),
        channel_partner_id=partner_id,
        is_primary=True,
    )
    if except_id:
        query = query.filter(ChannelPartnerContact.id != except_id)
    for row in query.all():
        row.is_primary = False


@channel_partners_bp.get('/references')
@require_capability('channel_partners.view', 'TENANT')
def references():
    projects = Project.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    ).order_by(Project.name).limit(500).all()
    users = User.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    ).order_by(User.name).limit(500).all()
    user_ids = [row.id for row in users]
    now = datetime.utcnow()
    role_rows = UserBusinessRole.query.join(
        BusinessRole,
        BusinessRole.id == UserBusinessRole.business_role_id,
    ).filter(
        UserBusinessRole.tenant_id == _tenant_id(),
        UserBusinessRole.user_id.in_(user_ids),
        UserBusinessRole.is_active.is_(True),
        UserBusinessRole.effective_from <= now,
        or_(
            UserBusinessRole.effective_to.is_(None),
            UserBusinessRole.effective_to > now,
        ),
        BusinessRole.is_active.is_(True),
    ).all() if user_ids else []
    role_map = {}
    for role_row in role_rows:
        role_map.setdefault(role_row.user_id, set()).add(
            role_row.business_role.key
        )
    user_rows = []
    for user in users:
        roles = sorted(role_map.get(user.id, set()))
        if roles:
            user_rows.append({'id': user.id, 'name': user.name, 'roles': roles})
    return jsonify({
        'projects': [{'id': row.id, 'name': row.name} for row in projects],
        'users': user_rows,
        'assignment_types': sorted(ASSIGNMENT_TYPES),
        'project_relationship_types': sorted(PROJECT_RELATIONSHIPS),
    })


@channel_partners_bp.get('')
@require_capability('channel_partners.view', 'TENANT')
def list_channel_partners():
    page, per_page = _page_args()
    query = ChannelPartner.query.options(
        selectinload(ChannelPartner.contacts),
        selectinload(ChannelPartner.project_associations).joinedload(
            ChannelPartnerProject.project
        ),
        selectinload(ChannelPartner.assignments).joinedload(
            ChannelPartnerAssignment.user
        ),
    ).filter_by(tenant_id=_tenant_id())
    active = str(request.args.get('active', 'true')).lower()
    if active in {'true', 'false'}:
        query = query.filter(ChannelPartner.is_active == (active == 'true'))
    partner_type = str(request.args.get('type') or '').upper()
    if partner_type:
        if partner_type not in PARTNER_TYPES:
            return jsonify({'error': 'Invalid Channel Partner type'}), 400
        query = query.filter(ChannelPartner.partner_type == partner_type)
    search = str(request.args.get('search') or '').strip()
    if search:
        like = f'%{search}%'
        query = query.filter(or_(
            ChannelPartner.name.ilike(like),
            ChannelPartner.organisation_name.ilike(like),
            ChannelPartner.code.ilike(like),
            ChannelPartner.city.ilike(like),
        ))
    project_id = request.args.get('project_id', type=int)
    if project_id:
        query = query.join(ChannelPartnerProject).filter(
            ChannelPartnerProject.tenant_id == _tenant_id(),
            ChannelPartnerProject.project_id == project_id,
            ChannelPartnerProject.is_active.is_(True),
        )
    assignment_type = str(
        request.args.get('assignment_type') or ''
    ).upper()
    assigned_user_id = request.args.get('assigned_user_id', type=int)
    if assignment_type or assigned_user_id:
        query = query.join(ChannelPartnerAssignment).filter(
            ChannelPartnerAssignment.tenant_id == _tenant_id(),
            ChannelPartnerAssignment.is_active.is_(True),
        )
        if assignment_type:
            query = query.filter(
                ChannelPartnerAssignment.assignment_type == assignment_type
            )
        if assigned_user_id:
            query = query.filter(
                ChannelPartnerAssignment.user_id == assigned_user_id
            )
    visible_ids = _visible_assignment_user_ids(request.current_user)
    if visible_ids is not None:
        visible_partner_ids = db.session.query(
            ChannelPartnerAssignment.channel_partner_id
        ).filter(
            ChannelPartnerAssignment.tenant_id == _tenant_id(),
            ChannelPartnerAssignment.is_active.is_(True),
            ChannelPartnerAssignment.user_id.in_(visible_ids),
        )
        query = query.filter(ChannelPartner.id.in_(visible_partner_ids))
    query = query.distinct()
    total = query.count()
    rows = query.order_by(
        ChannelPartner.name, ChannelPartner.id
    ).offset((page - 1) * per_page).limit(per_page).all()
    reveal = _can_reveal()
    serialized = []
    for row in rows:
        item = row.to_dict(reveal_sensitive=reveal)
        item['project_associations'] = [
            link.to_dict() for link in row.project_associations
            if link.is_active
        ]
        item['assignments'] = [
            assignment.to_dict() for assignment in row.assignments
            if assignment.is_active
        ]
        serialized.append(item)
    return jsonify({
        'channel_partners': serialized,
        'pagination': {'page': page, 'per_page': per_page, 'total': total},
    })


@channel_partners_bp.post('')
@require_capability('channel_partners.create', 'TENANT')
def create_channel_partner():
    data = request.get_json() or {}
    partner_type = str(data.get('partner_type') or '').upper()
    name = str(data.get('name') or '').strip()
    if partner_type not in PARTNER_TYPES or not name:
        return jsonify({
            'error': 'Name and valid Channel Partner type are required',
        }), 400
    code = str(data.get('code') or f'CP-{uuid4().hex[:10]}').strip().upper()
    if ChannelPartner.query.filter_by(
        tenant_id=_tenant_id(), code=code
    ).first():
        return jsonify({'error': 'Channel Partner code already exists'}), 409
    row = ChannelPartner(
        tenant_id=_tenant_id(),
        code=code,
        partner_type=partner_type,
        name=name,
        created_by=request.current_user.id,
        updated_by=request.current_user.id,
    )
    try:
        _apply_profile(row, data)
        db.session.add(row)
        db.session.flush()
        for owner_type, payload_key in (
            ('SALES_MANAGER', 'sales_manager_id'),
            ('RELATIONSHIP_MANAGER', 'relationship_manager_id'),
        ):
            owner_user_id = data.get(payload_key)
            if not owner_user_id:
                continue
            owner_user = _validate_assignment_user(owner_user_id, owner_type)
            db.session.add(ChannelPartnerAssignment(
                tenant_id=_tenant_id(),
                channel_partner_id=row.id,
                user_id=owner_user.id,
                assignment_type=owner_type,
                assigned_by=request.current_user.id,
            ))
        correlation_id = _cid()
        _audit(
            'channel_partner_created', 'ChannelPartner', row.id,
            None, row.to_dict(include_details=True, reveal_sensitive=True),
            correlation_id,
        )
        db.session.commit()
        return jsonify({
            'channel_partner': row.to_dict(
                include_details=True, reveal_sensitive=_can_reveal()
            ),
            'correlation_id': correlation_id,
        }), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


@channel_partners_bp.get('/<int:partner_id>')
@require_capability('channel_partners.view', 'TENANT')
def get_channel_partner(partner_id):
    row = _partner(partner_id)
    if not row:
        return jsonify({'error': 'Channel Partner not found'}), 404
    if not _can_view_partner(row, request.current_user):
        return jsonify({'error': 'Permission denied'}), 403
    reveal = _can_reveal()
    return jsonify({
        'channel_partner': row.to_dict(
            include_details=True, reveal_sensitive=reveal
        ),
        'permissions': {'reveal_sensitive': reveal},
    })


@channel_partners_bp.put('/<int:partner_id>')
@require_capability('channel_partners.edit', 'TENANT')
def update_channel_partner(partner_id):
    row = _partner(partner_id)
    if not row:
        return jsonify({'error': 'Channel Partner not found'}), 404
    data = request.get_json() or {}
    old = row.to_dict(include_details=True, reveal_sensitive=True)
    try:
        _apply_profile(row, data)
        row.updated_by = request.current_user.id
        correlation_id = _cid()
        new = row.to_dict(include_details=True, reveal_sensitive=True)
        _audit(
            'channel_partner_updated', 'ChannelPartner', row.id,
            old, new, correlation_id,
        )
        changed = {
            key for key in IMPORTANT_PROFILE_FIELDS
            if key in data and old.get(key) != new.get(key)
        }
        if changed:
            notify_channel_partner_profile_change(row, correlation_id)
        db.session.commit()
        return jsonify({
            'channel_partner': row.to_dict(
                include_details=True, reveal_sensitive=_can_reveal()
            ),
            'correlation_id': correlation_id,
        })
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


def _set_partner_active(partner_id, active):
    row = _partner(partner_id)
    if not row:
        return jsonify({'error': 'Channel Partner not found'}), 404
    old = row.to_dict(include_details=True, reveal_sensitive=True)
    row.is_active = active
    row.archived_at = None if active else datetime.utcnow()
    row.updated_by = request.current_user.id
    correlation_id = _cid()
    _audit(
        'channel_partner_restored' if active else 'channel_partner_archived',
        'ChannelPartner', row.id, old,
        row.to_dict(include_details=True, reveal_sensitive=True),
        correlation_id,
    )
    db.session.commit()
    return jsonify({
        'channel_partner': row.to_dict(
            include_details=True, reveal_sensitive=_can_reveal()
        ),
        'correlation_id': correlation_id,
    })


@channel_partners_bp.post('/<int:partner_id>/archive')
@require_capability('channel_partners.archive', 'TENANT')
def archive_channel_partner(partner_id):
    return _set_partner_active(partner_id, False)


@channel_partners_bp.post('/<int:partner_id>/restore')
@require_capability('channel_partners.archive', 'TENANT')
def restore_channel_partner(partner_id):
    return _set_partner_active(partner_id, True)


@channel_partners_bp.post('/<int:partner_id>/contacts')
@require_capability('channel_partners.manage_contacts', 'TENANT')
def create_contact(partner_id):
    partner = _partner(partner_id, include_inactive=False)
    if not partner:
        return jsonify({'error': 'Active Channel Partner not found'}), 404
    data = request.get_json() or {}
    row = ChannelPartnerContact(
        tenant_id=_tenant_id(),
        channel_partner_id=partner.id,
        name=str(data.get('name') or '').strip(),
        created_by=request.current_user.id,
        updated_by=request.current_user.id,
    )
    try:
        _contact_payload(row, data)
        if row.is_primary:
            _demote_other_primary_contacts(partner.id)
        db.session.add(row)
        db.session.flush()
        correlation_id = _cid()
        _audit(
            'channel_partner_contact_created', 'ChannelPartnerContact',
            row.id, None, row.to_dict(reveal_sensitive=True), correlation_id,
        )
        db.session.commit()
        return jsonify({
            'contact': row.to_dict(reveal_sensitive=_can_reveal()),
            'correlation_id': correlation_id,
        }), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


@channel_partners_bp.put('/<int:partner_id>/contacts/<int:contact_id>')
@require_capability('channel_partners.manage_contacts', 'TENANT')
def update_contact(partner_id, contact_id):
    row = _contact(partner_id, contact_id)
    if not row:
        return jsonify({'error': 'Channel Partner contact not found'}), 404
    data = request.get_json() or {}
    old = row.to_dict(reveal_sensitive=True)
    try:
        _contact_payload(row, data)
        row.updated_by = request.current_user.id
        if row.is_primary:
            _demote_other_primary_contacts(partner_id, except_id=row.id)
        correlation_id = _cid()
        _audit(
            'channel_partner_contact_updated', 'ChannelPartnerContact',
            row.id, old, row.to_dict(reveal_sensitive=True), correlation_id,
        )
        db.session.commit()
        return jsonify({
            'contact': row.to_dict(reveal_sensitive=_can_reveal()),
            'correlation_id': correlation_id,
        })
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


def _set_contact_active(partner_id, contact_id, active):
    row = _contact(partner_id, contact_id)
    if not row:
        return jsonify({'error': 'Channel Partner contact not found'}), 404
    old = row.to_dict(reveal_sensitive=True)
    row.is_active = active
    row.archived_at = None if active else datetime.utcnow()
    if not active:
        row.is_primary = False
    row.updated_by = request.current_user.id
    correlation_id = _cid()
    _audit(
        'channel_partner_contact_restored'
        if active else 'channel_partner_contact_archived',
        'ChannelPartnerContact', row.id, old,
        row.to_dict(reveal_sensitive=True), correlation_id,
    )
    db.session.commit()
    return jsonify({
        'contact': row.to_dict(reveal_sensitive=_can_reveal()),
        'correlation_id': correlation_id,
    })


@channel_partners_bp.post(
    '/<int:partner_id>/contacts/<int:contact_id>/archive'
)
@require_capability('channel_partners.manage_contacts', 'TENANT')
def archive_contact(partner_id, contact_id):
    return _set_contact_active(partner_id, contact_id, False)


@channel_partners_bp.post(
    '/<int:partner_id>/contacts/<int:contact_id>/restore'
)
@require_capability('channel_partners.manage_contacts', 'TENANT')
def restore_contact(partner_id, contact_id):
    return _set_contact_active(partner_id, contact_id, True)


@channel_partners_bp.post('/<int:partner_id>/projects')
@require_capability('channel_partners.manage_projects', 'TENANT')
def add_project_association(partner_id):
    partner = _partner(partner_id, include_inactive=False)
    if not partner:
        return jsonify({'error': 'Active Channel Partner not found'}), 404
    data = request.get_json() or {}
    relationship_type = str(
        data.get('relationship_type') or 'ACTIVE'
    ).upper()
    if relationship_type not in PROJECT_RELATIONSHIPS:
        return jsonify({'error': 'Invalid project relationship type'}), 400
    try:
        project = _project(data.get('project_id'))
        if not project:
            raise ValueError('Project is required')
        existing = ChannelPartnerProject.query.filter_by(
            tenant_id=_tenant_id(),
            channel_partner_id=partner.id,
            project_id=project.id,
            relationship_type=relationship_type,
            is_active=True,
        ).first()
        if existing:
            return jsonify({'error': 'Project relationship already exists'}), 409
        row = ChannelPartnerProject(
            tenant_id=_tenant_id(),
            channel_partner_id=partner.id,
            project_id=project.id,
            relationship_type=relationship_type,
            created_by=request.current_user.id,
        )
        if relationship_type == 'HISTORICAL':
            row.is_active = False
            row.effective_to = datetime.utcnow()
        db.session.add(row)
        db.session.flush()
        correlation_id = _cid()
        _audit(
            'channel_partner_project_added', 'ChannelPartnerProject',
            row.id, None, row.to_dict(), correlation_id,
        )
        db.session.commit()
        return jsonify({
            'project_association': row.to_dict(),
            'correlation_id': correlation_id,
        }), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


@channel_partners_bp.put(
    '/<int:partner_id>/projects/<int:association_id>'
)
@require_capability('channel_partners.manage_projects', 'TENANT')
def update_project_association(partner_id, association_id):
    row = ChannelPartnerProject.query.filter_by(
        id=association_id,
        tenant_id=_tenant_id(),
        channel_partner_id=partner_id,
    ).first()
    if not row:
        return jsonify({'error': 'Project relationship not found'}), 404
    data = request.get_json() or {}
    relationship_type = str(
        data.get('relationship_type', row.relationship_type)
    ).upper()
    if relationship_type not in PROJECT_RELATIONSHIPS:
        return jsonify({'error': 'Invalid project relationship type'}), 400
    old = row.to_dict()
    row.relationship_type = relationship_type
    row.is_active = relationship_type != 'HISTORICAL'
    row.effective_to = None if row.is_active else datetime.utcnow()
    correlation_id = _cid()
    _audit(
        'channel_partner_project_updated', 'ChannelPartnerProject',
        row.id, old, row.to_dict(), correlation_id,
    )
    db.session.commit()
    return jsonify({
        'project_association': row.to_dict(),
        'correlation_id': correlation_id,
    })


@channel_partners_bp.post('/<int:partner_id>/assignments')
@require_capability('channel_partners.assign', 'TENANT')
def add_assignment(partner_id):
    partner = _partner(partner_id, include_inactive=False)
    if not partner:
        return jsonify({'error': 'Active Channel Partner not found'}), 404
    data = request.get_json() or {}
    assignment_type = str(data.get('assignment_type') or '').upper()
    if assignment_type not in ASSIGNMENT_TYPES:
        return jsonify({'error': 'Invalid assignment type'}), 400
    try:
        user = _validate_assignment_user(
            data.get('user_id'), assignment_type
        )
        if assignment_type != 'SECONDARY_RM':
            current_rows = ChannelPartnerAssignment.query.filter_by(
                tenant_id=_tenant_id(),
                channel_partner_id=partner.id,
                assignment_type=assignment_type,
                is_active=True,
            ).all()
            for current in current_rows:
                current.is_active = False
                current.effective_to = datetime.utcnow()
        elif ChannelPartnerAssignment.query.filter_by(
            tenant_id=_tenant_id(),
            channel_partner_id=partner.id,
            user_id=user.id,
            assignment_type=assignment_type,
            is_active=True,
        ).first():
            return jsonify({'error': 'Secondary RM is already assigned'}), 409
        row = ChannelPartnerAssignment(
            tenant_id=_tenant_id(),
            channel_partner_id=partner.id,
            user_id=user.id,
            assignment_type=assignment_type,
            assigned_by=request.current_user.id,
        )
        db.session.add(row)
        db.session.flush()
        correlation_id = _cid()
        _audit(
            'channel_partner_assigned', 'ChannelPartnerAssignment',
            row.id, None, row.to_dict(), correlation_id,
        )
        notify_channel_partner_assignment(user, partner, correlation_id)
        db.session.commit()
        return jsonify({
            'assignment': row.to_dict(),
            'correlation_id': correlation_id,
        }), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


@channel_partners_bp.post(
    '/<int:partner_id>/assignments/<int:assignment_id>/archive'
)
@require_capability('channel_partners.assign', 'TENANT')
def archive_assignment(partner_id, assignment_id):
    row = ChannelPartnerAssignment.query.filter_by(
        id=assignment_id,
        tenant_id=_tenant_id(),
        channel_partner_id=partner_id,
        is_active=True,
    ).first()
    if not row:
        return jsonify({'error': 'Active assignment not found'}), 404
    old = row.to_dict()
    row.is_active = False
    row.effective_to = datetime.utcnow()
    correlation_id = _cid()
    _audit(
        'channel_partner_assignment_archived',
        'ChannelPartnerAssignment', row.id, old, row.to_dict(),
        correlation_id,
    )
    db.session.commit()
    return jsonify({
        'assignment': row.to_dict(), 'correlation_id': correlation_id,
    })


@channel_partners_bp.post('/<int:partner_id>/notes')
@require_capability('channel_partners.edit', 'TENANT')
def add_note(partner_id):
    partner = _partner(partner_id, include_inactive=False)
    if not partner:
        return jsonify({'error': 'Active Channel Partner not found'}), 404
    content = str((request.get_json() or {}).get('content') or '').strip()
    if not content:
        return jsonify({'error': 'Note content is required'}), 400
    row = ChannelPartnerNote(
        tenant_id=_tenant_id(),
        channel_partner_id=partner.id,
        content=content,
        created_by=request.current_user.id,
    )
    db.session.add(row)
    db.session.flush()
    correlation_id = _cid()
    _audit(
        'channel_partner_note_added', 'ChannelPartnerNote',
        row.id, None, row.to_dict(), correlation_id,
    )
    db.session.commit()
    return jsonify({
        'note': row.to_dict(), 'correlation_id': correlation_id,
    }), 201


@channel_partners_bp.get('/<int:partner_id>/timeline')
@require_capability('channel_partners.view', 'TENANT')
def channel_partner_timeline(partner_id):
    partner = _partner(partner_id)
    if not partner:
        return jsonify({'error': 'Channel Partner not found'}), 404
    if not _can_view_partner(partner, request.current_user):
        return jsonify({'error': 'Permission denied'}), 403
    limit = min(200, max(10, request.args.get('limit', 100, type=int)))
    entries = []
    participants = VisitParticipant.query.filter_by(
        tenant_id=_tenant_id(),
        participant_type='CHANNEL_PARTNER',
        reference_id=partner.id,
    ).limit(limit).all()
    visit_ids = [row.visit_id for row in participants]
    visits = Visit.query.options(
        joinedload(Visit.location), joinedload(Visit.project)
    ).filter(
        Visit.tenant_id == _tenant_id(),
        Visit.id.in_(visit_ids),
    ).limit(limit).all() if visit_ids else []
    for row in visits:
        entries.append({
            'type': 'VISIT',
            'timestamp': to_ist_str(row.created_at),
            'title': row.purpose or row.visit_type_key.replace('_', ' ').title(),
            'summary': f'{row.status_key} at {row.location.name}',
            'reference_id': row.id,
            '_sort': row.created_at,
        })
    notes = ChannelPartnerNote.query.options(
        joinedload(ChannelPartnerNote.author)
    ).filter_by(
        tenant_id=_tenant_id(),
        channel_partner_id=partner.id,
        is_active=True,
    ).order_by(ChannelPartnerNote.created_at.desc()).limit(limit).all()
    for row in notes:
        entries.append({
            'type': 'NOTE',
            'timestamp': to_ist_str(row.created_at),
            'title': 'Note',
            'summary': row.content,
            'reference_id': row.id,
            '_sort': row.created_at,
        })
    assignments = ChannelPartnerAssignment.query.options(
        joinedload(ChannelPartnerAssignment.user)
    ).filter_by(
        tenant_id=_tenant_id(),
        channel_partner_id=partner.id,
    ).order_by(ChannelPartnerAssignment.created_at.desc()).limit(limit).all()
    for row in assignments:
        entries.append({
            'type': 'ASSIGNMENT',
            'timestamp': to_ist_str(row.created_at),
            'title': row.assignment_type.replace('_', ' ').title(),
            'summary': row.user.name if row.user else 'Unknown user',
            'reference_id': row.id,
            '_sort': row.created_at,
        })
    activities = ActivityLog.query.filter_by(
        tenant_id=_tenant_id(),
        module='channel_partners',
        resource_type='ChannelPartner',
        resource_id=partner.id,
    ).order_by(ActivityLog.created_at.desc()).limit(limit).all()
    for row in activities:
        entries.append({
            'type': 'ACTIVITY',
            'timestamp': to_ist_str(row.created_at),
            'title': row.action.replace('_', ' ').title(),
            'summary': row.description or '',
            'reference_id': row.id,
            '_sort': row.created_at,
        })
    notifications = NotificationEvent.query.filter_by(
        tenant_id=_tenant_id(),
        channel_partner_id=partner.id,
    ).order_by(NotificationEvent.created_at.desc()).limit(limit).all()
    for row in notifications:
        entries.append({
            'type': 'NOTIFICATION',
            'timestamp': to_ist_str(row.created_at),
            'title': row.title,
            'summary': row.status,
            'reference_id': row.id,
            '_sort': row.created_at,
        })
    entries.sort(key=lambda item: item['_sort'] or datetime.min, reverse=True)
    for item in entries:
        item.pop('_sort', None)
    return jsonify({
        'timeline': entries[:limit],
        'future_tasks': [],
        'future_task_foundation': {
            'supported': True,
            'implemented': False,
            'relationship_key': 'channel_partner_id',
        },
    })
