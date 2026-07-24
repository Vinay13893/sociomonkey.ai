"""Canonical callback workflow helpers."""
from datetime import datetime

from app.models.base import db
from app.models.lead import CallbackReminder, Lead
from app.models.user import User
from app.utils.activity import log_activity
from app.utils.correlation import correlation_id as ensure_correlation_id
from app.utils.time_utils import parse_business_datetime_to_utc_naive


CALLBACK_PENDING_ERROR = 'A pending callback already exists for this lead. Close it with a note before creating a new one.'


def resolve_callback_owner(lead: Lead, actor: User):
    """Return the working user for a callback without changing lead assignment."""
    if lead.assigned_to:
        return lead.assigned_to
    if actor and actor.role == 'team_member':
        return actor.id
    return None


def resolve_callback_manager(lead: Lead, assigned_user_id):
    if lead.sales_manager_id:
        return lead.sales_manager_id
    if assigned_user_id:
        assigned = User.query.get(assigned_user_id)
        if assigned:
            return assigned.manager_id
    return None


def find_pending_callback(lead_id):
    return (
        CallbackReminder.query
        .filter_by(lead_id=lead_id, status='pending')
        .order_by(CallbackReminder.callback_datetime.asc(), CallbackReminder.id.asc())
        .first()
    )


def create_callback_for_lead(
    lead, actor, raw_datetime, notes=None, correlation_id=None
):
    cb_dt = parse_business_datetime_to_utc_naive(raw_datetime)
    if cb_dt <= datetime.utcnow():
        raise ValueError('Callback time must be in the future')

    existing = find_pending_callback(lead.id)
    if existing:
        return None, existing, CALLBACK_PENDING_ERROR

    assigned_user_id = resolve_callback_owner(lead, actor)
    manager_id = resolve_callback_manager(lead, assigned_user_id)
    correlation_id = ensure_correlation_id(correlation_id)
    cb = CallbackReminder(
        lead_id=lead.id,
        tenant_id=lead.tenant_id,
        assigned_user_id=assigned_user_id,
        manager_id=manager_id,
        callback_datetime=cb_dt,
        notes=(notes or '').strip() or None,
        correlation_id=correlation_id,
        created_by=actor.id if actor else None,
    )
    db.session.add(cb)

    old_status = lead.status
    if old_status in ('new', 'follow_up', 'no_answer', 'callback_scheduled') and old_status != 'callback_scheduled':
        from app.services.pipeline_engine import transition_lead
        transition_lead(
            lead, 'callback_scheduled', actor=actor,
            source='CALLBACK_SCHEDULED',
            reason='Callback scheduled',
            context={'follow_up_completed': True},
            correlation_id=correlation_id,
            notify=False,
        )

    return cb, None, None


def reschedule_callback(callback: CallbackReminder, actor: User, raw_datetime, notes_marker=None):
    cb_dt = parse_business_datetime_to_utc_naive(raw_datetime)
    if cb_dt <= datetime.utcnow():
        raise ValueError('Callback time must be in the future')

    old_dt = callback.callback_datetime
    callback.callback_datetime = cb_dt
    callback.reminder_10_sent = False
    callback.reminder_due_sent = False
    if notes_marker is not None:
        callback.notes = (notes_marker or '').strip() or None
    return old_dt, cb_dt


def append_callback_closure_note(callback: CallbackReminder, actor: User, closure_note: str, label: str):
    from app.utils.time_utils import now_ist
    closed_at = now_ist().strftime('%d %b %Y %H:%M IST')
    actor_name = actor.name or actor.email or f'User {actor.id}'
    entry = f'[{label} by {actor_name} at {closed_at}] {closure_note}'
    callback.notes = f'{callback.notes}\n{entry}'.strip() if callback.notes else entry
    return entry


def complete_callback_record(callback: CallbackReminder, actor: User, closure_note: str):
    callback.status = 'completed'
    return append_callback_closure_note(callback, actor, closure_note, 'COMPLETED')


def cancel_callback_record(callback: CallbackReminder, actor: User, closure_note: str):
    callback.status = 'cancelled'
    return append_callback_closure_note(callback, actor, closure_note, 'CANCELLED')


def log_callback_activity(actor: User, action: str, lead: Lead, description: str, **kwargs):
    log_activity(
        actor.id,
        action,
        'leads',
        lead.id if lead else None,
        'Lead',
        description=description,
        **kwargs,
    )
