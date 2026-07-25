from datetime import datetime

from app.models.lead import Lead
from app import db
from flask import request as flask_request

VALID_STATUSES = [
    'new', 'no_answer', 'follow_up', 'callback_scheduled',
    'interested',
    'site_visit_planned', 'site_visit_done',
    'negotiation', 'booking_done',
    'not_interested', 'lost', 'junk',
]

# Backward-compat aliases: old DB values that may still exist before migration
STATUS_ALIASES = {
    'attempted': 'no_answer',
    'connected': 'follow_up',
}

# Human-readable labels
STATUS_LABELS = {
    'new':                 'New',
    'no_answer':           'No Answer',
    'follow_up':           'Follow Up',
    'callback_scheduled':  'Callback Scheduled',
    'interested':          'Interested',
    'site_visit_planned':  'Site Visit Planned',
    'site_visit_done':     'Site Visit Done',
    'negotiation':         'Negotiation',
    'booking_done':        'Booking Done',
    'not_interested':      'Not Interested',
    'lost':                'Lost',
    'junk':                'Junk',
    # legacy aliases (backward compat for old exports / activity logs)
    'attempted':           'No Answer (legacy)',
    'connected':           'Follow Up (legacy)',
}

def should_include_test_leads():
    try:
        raw = str(flask_request.args.get('show_test_data', '')).strip().lower()
    except RuntimeError:
        return False
    return raw in {'1', 'true', 'yes', 'on'}

def apply_test_lead_filter(query):
    if should_include_test_leads():
        return query
    return query.filter(Lead.is_test == False)


def _nonblank(column):
    return db.func.trim(db.func.coalesce(column, '')) != ''


def apply_valid_lead_capture_scope(query, tenant_id):
    """Apply the canonical LMS definition of a countable lead.

    Countable leads must be active, non-test unless explicitly requested by the
    caller, have a name and at least one contact channel, and have trustworthy
    provenance:
    - connected Meta/Google/etc. source rows require a processed ingestion log
    - manual/import rows are accepted only when they are user-created and not
      labelled as one of the connected source names
    """
    from app.models.ingestion import IngestedLeadLog, LeadSource
    from app.utils.lead_source_cutoff import lead_source_cutoff_for

    tenant_cutoff = lead_source_cutoff_for(tenant_id=tenant_id)

    processed_source_lead_ids = (
        db.session.query(IngestedLeadLog.lead_id)
        .join(LeadSource, IngestedLeadLog.source_id == LeadSource.id)
        .filter(IngestedLeadLog.tenant_id == tenant_id)
        .filter(LeadSource.tenant_id == tenant_id)
        .filter(LeadSource.is_active == True)
        .filter(IngestedLeadLog.status == 'processed')
        .filter(IngestedLeadLog.lead_id.isnot(None))
    )
    if tenant_cutoff:
        processed_source_lead_ids = processed_source_lead_ids.filter(
            IngestedLeadLog.received_at >= tenant_cutoff
        )

    connected_source_names = (
        db.session.query(db.func.lower(db.func.trim(LeadSource.name)))
        .filter(LeadSource.tenant_id == tenant_id)
        .filter(LeadSource.is_active == True)
        .filter(LeadSource.name.isnot(None))
        .filter(db.func.trim(LeadSource.name) != '')
        .distinct()
    )

    has_required_fields = db.and_(
        _nonblank(Lead.name),
        db.or_(
            _nonblank(Lead.phone),
            _nonblank(Lead.alternate_phone),
            _nonblank(Lead.email),
        ),
    )
    valid_manual_or_import = db.and_(
        Lead.created_by.isnot(None),
        db.or_(
            Lead.source.is_(None),
            db.func.trim(db.func.coalesce(Lead.source, '')) == '',
            ~db.func.lower(db.func.trim(Lead.source)).in_(connected_source_names),
        ),
    )

    return query.filter(has_required_fields).filter(db.or_(
        Lead.id.in_(processed_source_lead_ids.distinct()),
        valid_manual_or_import,
    ))


def _reporting_team_ids(user):
    """Union of user.id, everyone reporting to user via a real
    ReportingRelationship (set up through the Roles & Teams admin UI), and
    everyone reporting via the legacy manager_id hierarchy
    (user.team_members). Mirrors app.routes.action_items's
    _active_reporting_user_ids so that setting up real reporting lines
    immediately extends Lead visibility, without requiring every tenant to
    migrate off the legacy hierarchy first."""
    from app.models.organisation import ReportingRelationship

    now = datetime.utcnow()
    rows = ReportingRelationship.query.with_entities(
        ReportingRelationship.user_id
    ).filter(
        ReportingRelationship.tenant_id == user.tenant_id,
        ReportingRelationship.manager_id == user.id,
        ReportingRelationship.is_active == True,  # noqa: E712
        ReportingRelationship.effective_from <= now,
        db.or_(
            ReportingRelationship.effective_to.is_(None),
            ReportingRelationship.effective_to > now,
        ),
    ).all()
    ids = {user.id, *(row[0] for row in rows)}
    ids.update(tm.id for tm in user.team_members)
    return ids


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
                query = Lead.query.filter_by(is_active=True, tenant_id=scoped_tid)
                return apply_valid_lead_capture_scope(apply_test_lead_filter(query), scoped_tid)
        except RuntimeError:
            pass  # Outside of request context (tests, scripts)
        return apply_test_lead_filter(Lead.query.filter_by(is_active=True))

    if user.role == 'superadmin':
        query = Lead.query.filter_by(is_active=True, tenant_id=tid)
        return apply_valid_lead_capture_scope(apply_test_lead_filter(query), tid)

    if user.role == 'sales_manager':
        # Real ReportingRelationship rows (Roles & Teams admin UI) extend
        # this beyond the legacy manager_id hierarchy the moment a tenant
        # sets them up - see _reporting_team_ids.
        team_ids = _reporting_team_ids(user)
        query = Lead.query.filter(
            Lead.is_active == True,
            Lead.tenant_id == tid,
            db.or_(
                Lead.sales_manager_id == user.id,
                Lead.assigned_to == user.id,
                Lead.assigned_to.in_(team_ids),
                # A user can be a co-owner in the pre-sales slots even while
                # their legacy role is sales_manager (a Calling Manager is
                # commonly a legacy sales_manager today, until Phase A's
                # role admin lets tenants migrate off the legacy field).
                Lead.calling_manager_id == user.id,
                Lead.caller_id == user.id,
            )
        )
        return apply_valid_lead_capture_scope(apply_test_lead_filter(query), tid)

    if user.role == 'team_member':
        query = Lead.query.filter(
            Lead.is_active == True,
            Lead.tenant_id == tid,
            db.or_(
                Lead.assigned_to == user.id,
                Lead.calling_manager_id == user.id,
                Lead.caller_id == user.id,
            ),
        )
        return apply_valid_lead_capture_scope(apply_test_lead_filter(query), tid)

    return Lead.query.filter(Lead.id == -1)
