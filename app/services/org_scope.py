"""Project/location-scoped business-role pool resolution (Phase 13d).

The centralized scope-to-user-ids resolver the codebase was missing -
app.routes.action_items reimplements a version of this locally for Action
Items; this is the generalized version for auto-assignment, currently
consumed only by app.services.ingestion_engine's Calling Manager
auto-assign tier.
"""
from datetime import datetime

from app.models.base import db
from app.models.organisation import BusinessRole, OrganisationUnit, RoleAssignmentRotation, UserBusinessRole
from app.models.user import User


def root_unit_id(tenant_id):
    root = OrganisationUnit.query.filter_by(tenant_id=tenant_id, code='ROOT').first()
    return root.id if root else None


def _pool_user_ids(tenant_id, business_role_id, organisation_unit_id):
    if organisation_unit_id is None:
        return []
    rows = UserBusinessRole.query.with_entities(UserBusinessRole.user_id).filter(
        UserBusinessRole.tenant_id == tenant_id,
        UserBusinessRole.business_role_id == business_role_id,
        UserBusinessRole.organisation_unit_id == organisation_unit_id,
        UserBusinessRole.is_active == True,  # noqa: E712
    ).all()
    return [row[0] for row in rows]


def resolve_pool_for_role(tenant_id, role_key, organisation_unit_id=None):
    """Active users holding business role `role_key`, scoped to
    `organisation_unit_id` if it has any current holders, else falling back
    to the tenant's root (tenant-wide) unit. Returns
    (users, resolved_unit_id) - resolved_unit_id is whichever unit the pool
    actually came from, for round-robin state keying. Empty list + None
    when nobody holds this role anywhere in the tenant."""
    role = BusinessRole.query.filter(
        BusinessRole.key == role_key,
        db.or_(BusinessRole.tenant_id == tenant_id, BusinessRole.tenant_id.is_(None)),
    ).first()
    if not role:
        return [], None

    root_id = root_unit_id(tenant_id)
    user_ids = []
    resolved_unit_id = None
    if organisation_unit_id and organisation_unit_id != root_id:
        user_ids = _pool_user_ids(tenant_id, role.id, organisation_unit_id)
        resolved_unit_id = organisation_unit_id
    if not user_ids and root_id:
        user_ids = _pool_user_ids(tenant_id, role.id, root_id)
        resolved_unit_id = root_id
    if not user_ids:
        return [], None

    users = User.query.filter(
        User.id.in_(user_ids), User.tenant_id == tenant_id, User.is_active == True,  # noqa: E712
    ).order_by(User.id.asc()).all()
    if not users:
        return [], None
    return users, resolved_unit_id


def resolve_org_scoped_assignee(tenant_id, role_key, project_organisation_unit_id):
    """Round-robins among active holders of `role_key`, scoped to a
    project's organisation unit if it has any, else the tenant's root unit.
    Returns None if nobody holds this role anywhere in the tenant (leaves
    the caller free to leave that slot unassigned rather than erroring)."""
    pool, resolved_unit_id = resolve_pool_for_role(tenant_id, role_key, project_organisation_unit_id)
    if not pool:
        return None

    rotation = RoleAssignmentRotation.query.filter_by(
        tenant_id=tenant_id, business_role_key=role_key,
        organisation_unit_id=resolved_unit_id,
    ).first()
    if not rotation:
        rotation = RoleAssignmentRotation(
            tenant_id=tenant_id, business_role_key=role_key,
            organisation_unit_id=resolved_unit_id, last_index=0,
        )
        db.session.add(rotation)

    idx = rotation.last_index % len(pool)
    chosen = pool[idx]
    rotation.last_index = (idx + 1) % len(pool)
    rotation.updated_at = datetime.utcnow()
    return chosen
