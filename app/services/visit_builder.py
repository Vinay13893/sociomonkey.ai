"""Shared Visit construction/validation and Reception Lead-intake helpers.

Extracted from app.routes.visits so app.routes.pipeline and
app.routes.gallery_operations can build/validate Visits and look up/create
Leads without importing another route module. Every function here takes
tenant_id explicitly rather than reading request.current_user internally,
so callers stay in control of tenant scoping and these functions remain
easy to unit test in isolation.
"""

from app.models.channel_partner import ChannelPartner  # noqa: F401  (re-exported for callers)
from app.models.lead import Lead
from app.models.location import Location, MeetingRoom
from app.models.project import Project
from app.models.user import User
from app.models.visit import Visit, VisitStatusConfiguration, VisitTypeConfiguration
from app.utils.time_utils import parse_business_datetime_to_utc_naive

PRIORITIES = {'LOW', 'NORMAL', 'HIGH', 'URGENT'}


def parse_datetime(value, field):
    if value in (None, ''):
        return None
    try:
        return parse_business_datetime_to_utc_naive(value)
    except ValueError as exc:
        raise ValueError(f'{field} must be an ISO-8601 datetime') from exc


def validate_reference(tenant_id, model, value, label, required=False, active_only=False):
    if value in (None, ''):
        if required:
            raise ValueError(f'{label} is required')
        return None
    query = model.query.filter_by(id=int(value), tenant_id=tenant_id)
    if active_only and hasattr(model, 'is_active'):
        query = query.filter_by(is_active=True)
    row = query.first()
    if not row:
        raise ValueError(f'{label} was not found in this tenant')
    return row


def validate_user(tenant_id, value, label):
    return validate_reference(tenant_id, User, value, label)


def validate_configuration(tenant_id, model, internal_key, label, allow_inactive_key=None):
    key = str(internal_key or '').strip().upper()
    row = model.query.filter_by(tenant_id=tenant_id, internal_key=key).first()
    if not row or (not row.is_active and key != allow_inactive_key):
        raise ValueError(f'{label} is not active for this tenant')
    return key


def validate_visit_payload(tenant_id, data, current=None):
    location = validate_reference(
        tenant_id, Location, data.get('location_id', current.location_id if current else None),
        'Location', required=True, active_only=current is None,
    )
    room_value = data.get('meeting_room_id', current.meeting_room_id if current else None)
    room = validate_reference(tenant_id, MeetingRoom, room_value, 'Meeting room')
    if room and room.location_id != location.id:
        raise ValueError('Meeting room must belong to the visit location')

    project_value = data.get('project_id', current.project_id if current else None)
    lead_value = data.get('lead_id', current.lead_id if current else None)
    assigned_value = data.get('assigned_user_id', current.assigned_user_id if current else None)
    reception_value = data.get(
        'reception_assigned_user_id',
        current.reception_assigned_user_id if current else None,
    )
    escort_value = data.get('escort_user_id', current.escort_user_id if current else None)
    project = validate_reference(tenant_id, Project, project_value, 'Project')
    lead = validate_reference(tenant_id, Lead, lead_value, 'Lead')
    assigned = validate_user(tenant_id, assigned_value, 'Assigned user')
    reception = validate_user(tenant_id, reception_value, 'Reception user')
    escort = validate_user(tenant_id, escort_value, 'Escort user')

    visit_type_key = validate_configuration(
        tenant_id, VisitTypeConfiguration,
        data.get('visit_type_key', current.visit_type_key if current else None),
        'Visit type',
        current.visit_type_key if current else None,
    )
    status_key = validate_configuration(
        tenant_id, VisitStatusConfiguration,
        data.get('status_key', current.status_key if current else 'SCHEDULED'),
        'Visit status',
        current.status_key if current else None,
    )
    priority = str(data.get('priority', current.priority if current else 'NORMAL')).upper()
    if priority not in PRIORITIES:
        raise ValueError('Invalid visit priority')
    visitor_count = int(data.get(
        'visitor_count', current.visitor_count if current else 1
    ))
    if visitor_count < 1:
        raise ValueError('Visitor count must be positive')

    expected = parse_datetime(
        data.get('expected_arrival', current.expected_arrival if current else None),
        'Expected arrival',
    )
    check_in = parse_datetime(
        data.get('actual_check_in', current.actual_check_in if current else None),
        'Actual check-in',
    )
    check_out = parse_datetime(
        data.get('actual_check_out', current.actual_check_out if current else None),
        'Actual check-out',
    )
    if check_in and check_out and check_out < check_in:
        raise ValueError('Actual check-out cannot be before actual check-in')

    return {
        'location_id': location.id,
        'meeting_room_id': room.id if room else None,
        'project_id': project.id if project else None,
        'lead_id': lead.id if lead else None,
        'assigned_user_id': assigned.id if assigned else None,
        'reception_assigned_user_id': reception.id if reception else None,
        'escort_user_id': escort.id if escort else None,
        'visit_type_key': visit_type_key, 'status_key': status_key,
        'priority': priority, 'visitor_count': visitor_count,
        'expected_arrival': expected, 'actual_check_in': check_in,
        'actual_check_out': check_out,
    }


def find_duplicate_lead_by_phone(tenant_id, phone, force=False):
    """Exact-match phone duplicate check, mirroring app.routes.leads.create_lead.

    No phone normalization is applied, matching the existing behaviour in
    create_lead exactly (raw stripped-string comparison). force=True skips
    the check entirely, mirroring create_lead's superadmin-only override.
    Only considers is_active leads: a soft-deleted Lead (DELETE /api/leads/<id>)
    must not permanently block re-entering that phone number - it's invisible
    to every lookup/search already, so blocking creation on it is a dead end
    the caller (and Reception) has no way to resolve.
    """
    if force:
        return None
    phone_val = str(phone or '').strip()
    if not phone_val:
        return None
    return Lead.query.filter(
        Lead.phone == phone_val, Lead.tenant_id == tenant_id,
        Lead.is_active == True,
    ).first()


def create_lead_row(tenant_id, actor, name, phone=None, alternate_phone=None,
                     email=None, source=None, project_id=None, status='new',
                     budget_min=None, budget_max=None):
    """Construct (but do not add/commit) a Lead, mirroring create_lead's
    Lead(...) call exactly."""
    return Lead(
        name=name,
        phone=(phone or None),
        alternate_phone=(alternate_phone or None),
        email=(email or None),
        source=source,
        budget_min=budget_min,
        budget_max=budget_max,
        project_id=project_id,
        status=status,
        tenant_id=tenant_id,
        created_by=actor.id,
    )


def default_visit_assigned_user(lead, explicit_assigned_user_id):
    """A Visit's assigned_user_id defaults to the Lead's current owner at
    creation time only; nothing re-syncs it later if the Lead is reassigned.
    Explicit values always win."""
    if explicit_assigned_user_id not in (None, ''):
        return explicit_assigned_user_id
    return lead.assigned_to if lead else None


MANAGER_ROLES = {'sales_manager', 'superadmin', 'platform_owner'}


def sync_lead_owner_if_unset(lead, user):
    """When a Visit's responsible user is set (at walk-in creation or via a
    later reassignment) and the linked Lead has no owner recorded yet, give
    the Lead that same owner - routed into the correct ownership field for
    that user's role, mirroring the manager/member split
    POST /api/leads/bulk-assign already uses (assign_type='manager' vs
    'member'): a Sales Manager (or admin) picked from Reception is routing
    the lead for calling, so they belong in lead.sales_manager_id, not
    lead.assigned_to - assigning a manager must never masquerade as
    assigning the RM who actually works the lead.
    One-directional and only fires on a currently-empty field: never
    overwrites an existing manager/owner, so this can't silently reassign a
    Lead someone else already owns."""
    if not lead or not user:
        return
    if user.role in MANAGER_ROLES:
        if lead.sales_manager_id is None:
            lead.sales_manager_id = user.id
    else:
        if lead.assigned_to is None:
            lead.assigned_to = user.id


# The 4 lead co-ownership slots (app.models.lead.Lead), keyed by the string
# a caller passes explicitly - shared by POST /pipeline/leads/<id>/assign
# and Reception's walk-in/assignment "assigning as" picker, so both stay in
# sync with exactly one definition of what a "slot" is.
LEAD_OWNER_SLOTS = {
    'rm': 'assigned_to',
    'sales_manager': 'sales_manager_id',
    'calling_manager': 'calling_manager_id',
    'caller': 'caller_id',
}


def assign_lead_slot(lead, user_id, slot):
    """Explicitly set one of the Lead's 4 co-ownership slots. Unlike
    sync_lead_owner_if_unset, this is never inferred from the assignee's
    legacy role (a Caller and an RM can both be legacy team_member, and a
    Calling Manager and Sales Manager can both be legacy sales_manager - the
    role field alone can't disambiguate 4 slots) and it always overwrites,
    since the caller (Reception staff picking an explicit "assigning as"
    role) made a deliberate choice, not a passive default-if-empty nudge.
    No-ops silently on an unknown slot/missing lead/user so a malformed or
    absent slot never blocks the surrounding walk-in/assignment action."""
    field = LEAD_OWNER_SLOTS.get(slot)
    if not field or not lead or not user_id:
        return
    setattr(lead, field, user_id)


def active_planned_visit_for_lead(tenant_id, lead_id):
    """The Lead's current not-yet-arrived planned Visit, if any. SCHEDULED is
    the only status that precedes CHECKED_IN/NO_SHOW in the Reception state
    machine (see app.routes.gallery_operations._transition), so once a Visit
    moves past SCHEDULED it's no longer "planned" and shouldn't block a new
    one from being requested."""
    return Visit.query.filter(
        Visit.tenant_id == tenant_id, Visit.lead_id == lead_id,
        Visit.is_active.is_(True), Visit.status_key == 'SCHEDULED',
    ).order_by(Visit.expected_arrival.asc().nullslast()).first()
