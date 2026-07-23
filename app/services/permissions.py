"""Capability evaluation with a backward-compatible legacy-role fallback."""

from datetime import datetime

from app.models.organisation import (
    PermissionDefinition,
    RolePermission,
    UserBusinessRole,
    UserPermissionOverride,
)


SCOPE_RANK = {
    'OWN': 10,
    'TEAM': 20,
    'ORGANISATION_UNIT': 30,
    'PROJECT': 30,
    'TENANT': 40,
    'PLATFORM': 50,
}


LEGACY_CAPABILITIES = {
    'platform_owner': {'*': 'PLATFORM'},
    'superadmin': {'*': 'TENANT'},
    'sales_manager': {
        'organisation.view': 'TEAM',
        'organisation.users.create': 'TEAM',
        'organisation.users.edit': 'TEAM',
        'organisation.users.archive': 'TEAM',
        'leads.view': 'TEAM',
        'leads.edit': 'TEAM',
        'leads.assign': 'TEAM',
        'action_board.view': 'TEAM',
        'action_items.view': 'TEAM',
        'action_items.create': 'TEAM',
        'action_items.edit': 'TEAM',
        'action_items.assign': 'TEAM',
        'action_items.complete': 'TEAM',
        'action_items.archive': 'TEAM',
        'reports.view': 'TEAM',
        'notifications.view': 'OWN',
    },
    'team_member': {
        'organisation.view': 'OWN',
        'leads.view': 'OWN',
        'leads.edit': 'OWN',
        'action_board.view': 'OWN',
        'action_items.view': 'OWN',
        'action_items.create': 'OWN',
        'action_items.edit': 'OWN',
        'action_items.complete': 'OWN',
        'notifications.view': 'OWN',
    },
}


def _scope_matches(grant_scope, requested_scope, grant_ref=None, requested_ref=None):
    if grant_scope == 'PLATFORM':
        return True
    if grant_scope == 'TENANT' and requested_scope != 'PLATFORM':
        return True
    if grant_scope == requested_scope:
        if grant_ref is not None:
            return requested_ref is not None and str(grant_ref) == str(requested_ref)
        return True
    return SCOPE_RANK.get(grant_scope, 0) >= SCOPE_RANK.get(requested_scope, 0)


def _legacy_allows(user, capability, scope):
    grants = LEGACY_CAPABILITIES.get(getattr(user, 'role', ''), {})
    granted_scope = grants.get(capability) or grants.get('*')
    return bool(granted_scope and _scope_matches(granted_scope, scope))


def capability_decision(user, capability, scope='OWN', scope_ref_id=None):
    """Return an auditable permission decision without mutating state."""
    if not user or not getattr(user, 'is_active', False):
        return {'allowed': False, 'source': 'inactive_user', 'scope': None}

    permission = PermissionDefinition.query.filter_by(key=capability, is_active=True).first()
    if not permission:
        allowed = _legacy_allows(user, capability, scope)
        return {
            'allowed': allowed,
            'source': 'legacy_fallback' if allowed else 'undefined_capability',
            'scope': scope if allowed else None,
        }

    now = datetime.utcnow()
    tenant_id = getattr(user, 'tenant_id', None)
    overrides = UserPermissionOverride.query.filter(
        UserPermissionOverride.user_id == user.id,
        UserPermissionOverride.tenant_id == tenant_id,
        UserPermissionOverride.permission_id == permission.id,
        UserPermissionOverride.is_active == True,  # noqa: E712
        UserPermissionOverride.effective_from <= now,
        (
            (UserPermissionOverride.effective_to.is_(None))
            | (UserPermissionOverride.effective_to > now)
        ),
    ).order_by(UserPermissionOverride.id.desc()).all()
    matching_overrides = [
        row for row in overrides
        if _scope_matches(row.scope_type, scope, row.scope_ref_id, scope_ref_id)
    ]
    if any(row.effect == 'DENY' for row in matching_overrides):
        return {'allowed': False, 'source': 'user_override_deny', 'scope': None}
    if any(row.effect == 'ALLOW' for row in matching_overrides):
        row = next(row for row in matching_overrides if row.effect == 'ALLOW')
        return {'allowed': True, 'source': 'user_override_allow', 'scope': row.scope_type}

    assignments = UserBusinessRole.query.filter(
        UserBusinessRole.user_id == user.id,
        UserBusinessRole.tenant_id == tenant_id,
        UserBusinessRole.is_active == True,  # noqa: E712
        UserBusinessRole.effective_from <= now,
        ((UserBusinessRole.effective_to.is_(None)) | (UserBusinessRole.effective_to > now)),
    ).all()
    role_ids = [row.business_role_id for row in assignments]
    if role_ids:
        grants = RolePermission.query.filter(
            RolePermission.business_role_id.in_(role_ids),
            RolePermission.permission_id == permission.id,
        ).all()
        matching = [
            row for row in grants
            if _scope_matches(row.scope_type, scope, row.scope_ref_id, scope_ref_id)
        ]
        if any(row.effect == 'DENY' for row in matching):
            return {'allowed': False, 'source': 'role_deny', 'scope': None}
        if matching:
            best = max(matching, key=lambda row: SCOPE_RANK.get(row.scope_type, 0))
            return {'allowed': True, 'source': 'business_role', 'scope': best.scope_type}

    allowed = _legacy_allows(user, capability, scope)
    return {
        'allowed': allowed,
        'source': 'legacy_fallback' if allowed else 'no_grant',
        'scope': scope if allowed else None,
    }


def has_capability(user, capability, scope='OWN', scope_ref_id=None):
    return capability_decision(user, capability, scope, scope_ref_id)['allowed']
