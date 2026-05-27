from app.models.lead import Lead
from app import db

VALID_STATUSES = [
    'new', 'attempted', 'connected', 'interested',
    'site_visit_planned', 'site_visit_done',
    'negotiation', 'booking_done', 'lost', 'junk',
]


def get_user_visible_leads(user):
    """Return a SQLAlchemy query filtered to leads visible to *user*, scoped by tenant."""
    tid = user.tenant_id

    # Platform owner — cross-tenant analytics (should not be used for direct lead ops)
    if user.role == 'platform_owner':
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
