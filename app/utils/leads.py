from app.models.lead import Lead
from app import db
from flask import request as flask_request

VALID_STATUSES = [
    'new', 'attempted', 'connected', 'interested',
    'site_visit_planned', 'site_visit_done',
    'negotiation', 'booking_done', 'lost', 'junk',
]


def get_user_visible_leads(user):
    """Return a SQLAlchemy query filtered to leads visible to *user*, scoped by tenant.

    For platform_owner, the active tenant is taken from request.current_tenant_id
    (set by the auth middleware when X-Tenant-Slug header is present).  This
    ensures the same tenant isolation that all other endpoints already enjoy.
    """
    tid = user.tenant_id

    # Platform owner — use the request-scoped tenant when drilling into a tenant.
    # Falls back to cross-tenant (all) if no tenant context is active.
    if user.role == 'platform_owner':
        try:
            scoped_tid = flask_request.current_tenant_id
            if scoped_tid and scoped_tid != user.tenant_id:
                return Lead.query.filter_by(is_active=True, tenant_id=scoped_tid)
        except RuntimeError:
            pass  # Outside of request context (tests, scripts)
        return Lead.query.filter_by(is_active=True)

    if user.role == 'superadmin':
        return Lead.query.filter_by(is_active=True, tenant_id=tid)

    if user.role == 'sales_manager':
        team_ids = [tm.id for tm in user.team_members]
        return Lead.query.filter(
            Lead.is_active == True,
            Lead.tenant_id == tid,
            db.or_(
                Lead.sales_manager_id == user.id,
                Lead.assigned_to == user.id,
                Lead.assigned_to.in_(team_ids),
            )
        )

    if user.role == 'team_member':
        return Lead.query.filter(
            Lead.is_active == True,
            Lead.tenant_id == tid,
            Lead.assigned_to == user.id,
        )

    return Lead.query.filter(Lead.id == -1)
