"""
Notification event enqueueing (Phase M1 foundation).

Phase M1 only enqueues NotificationEvent rows. Delivery (push send, batching,
retry) is intentionally out of scope; that ships in a later phase wired to a
Vercel Cron worker that drains queued rows and posts to Web Push / FCM.

The deep_link strings follow the canonical tenant URL structure already used
by the SPA router (/:slug/:tab/lead/:id).
"""
from datetime import datetime
from datetime import timezone as _tz

from app.models.base import db
from app.models.push import NotificationEvent
from app.utils.time_utils import IST


def _tenant_slug_for_user(user) -> str:
    return getattr(getattr(user, 'tenant', None), 'slug', None) or ''


def _build_lead_deep_link(tenant_slug: str, tab: str, lead_id) -> str:
    if not tenant_slug:
        return '/'
    if lead_id:
        return f'/{tenant_slug}/{tab}/lead/{lead_id}'
    return f'/{tenant_slug}/{tab}'


def _existing_event(idempotency_key):
    if not idempotency_key:
        return None
    return NotificationEvent.query.filter_by(idempotency_key=idempotency_key).first()


def enqueue_lead_assigned(user, lead, correlation_id=None, idempotency_key=None) -> NotificationEvent:
    existing = _existing_event(idempotency_key)
    if existing:
        return existing
    slug = _tenant_slug_for_user(user)
    project_name = getattr(getattr(lead, 'project', None), 'name', None) or ''
    body = lead.name or f'Lead #{lead.id}'
    if project_name:
        body = f'{body} \u00b7 {project_name}'
    ev = NotificationEvent(
        tenant_id=getattr(user, 'tenant_id', None),
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        user_id=user.id,
        event_type='lead_assigned',
        lead_id=lead.id,
        title='New Lead Assigned',
        body=body,
        deep_link=_build_lead_deep_link(slug, 'leads', lead.id),
        payload={'lead_id': lead.id, 'lead_name': lead.name, 'project_name': project_name},
        status='queued',
        scheduled_for=datetime.utcnow(),
    )
    db.session.add(ev)
    return ev


def enqueue_lead_reassigned(user, lead, correlation_id=None, idempotency_key=None) -> NotificationEvent:
    existing = _existing_event(idempotency_key)
    if existing:
        return existing
    slug = _tenant_slug_for_user(user)
    ev = NotificationEvent(
        tenant_id=getattr(user, 'tenant_id', None),
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        user_id=user.id,
        event_type='lead_reassigned',
        lead_id=lead.id,
        title='Lead Reassigned',
        body='New lead available',
        deep_link=_build_lead_deep_link(slug, 'leads', lead.id),
        payload={'lead_id': lead.id, 'lead_name': lead.name},
        status='queued',
        scheduled_for=datetime.utcnow(),
    )
    db.session.add(ev)
    return ev


def enqueue_visit_assignment(user, visit, correlation_id=None,
                             idempotency_key=None) -> NotificationEvent:
    """Queue a push event for a Gallery Operations Visit handoff."""
    existing = _existing_event(idempotency_key)
    if existing:
        return existing
    slug = _tenant_slug_for_user(user)
    location_name = getattr(getattr(visit, 'location', None), 'name', None) or ''
    purpose = getattr(visit, 'purpose', None) or 'Visit'
    body = f'{purpose} at {location_name}' if location_name else purpose
    ev = NotificationEvent(
        tenant_id=getattr(user, 'tenant_id', None),
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        user_id=user.id,
        event_type='visit_assigned',
        lead_id=getattr(visit, 'lead_id', None),
        title='Visit Assigned',
        body=body,
        deep_link=f'/{slug}/reception' if slug else '/',
        payload={
            'visit_id': visit.id,
            'location_id': visit.location_id,
            'location_name': location_name,
            'purpose': purpose,
        },
        status='queued',
        scheduled_for=datetime.utcnow(),
    )
    db.session.add(ev)
    return ev


def enqueue_callback_event(user, callback, kind: str, scheduled_for: datetime = None,
                           correlation_id=None, idempotency_key=None) -> NotificationEvent:
    """
    kind: 'due_soon' (10-min warning) | 'due_now' | 'overdue'
    """
    type_map = {
        'due_soon': ('callback_due_soon', 'Callback in 10 Minutes'),
        'due_now':  ('callback_due_now',  'Callback Due Now'),
        'overdue':  ('callback_overdue',  'Overdue Callback'),
    }
    event_type, title = type_map.get(kind, ('callback_due_now', 'Callback Due Now'))
    existing = _existing_event(idempotency_key)
    if existing:
        return existing
    slug = _tenant_slug_for_user(user)
    lead = getattr(callback, 'lead', None)
    lead_name = (lead.name if lead else None) or f'Lead #{getattr(callback, "lead_id", "")}'
    # Include IST time in push body so the user sees the actual scheduled time
    cb_dt = getattr(callback, 'callback_datetime', None)
    if cb_dt:
        cb_ist = cb_dt.replace(tzinfo=_tz.utc).astimezone(IST).strftime('%I:%M %p IST')
        body = f'{lead_name} · {cb_ist}'
    else:
        body = lead_name
    ev = NotificationEvent(
        tenant_id=getattr(callback, 'tenant_id', None) or getattr(user, 'tenant_id', None),
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        user_id=user.id,
        event_type=event_type,
        lead_id=getattr(callback, 'lead_id', None),
        callback_id=getattr(callback, 'id', None),
        title=title,
        body=body,
        deep_link=_build_lead_deep_link(slug, 'action-board', getattr(callback, 'lead_id', None)),
        payload={
            'callback_id': getattr(callback, 'id', None),
            'lead_id': getattr(callback, 'lead_id', None),
            'lead_name': lead_name,
            # Store UTC ISO for machine use; display string in IST for the notification body
            'callback_at': callback.callback_datetime.isoformat() if getattr(callback, 'callback_datetime', None) else None,
            'callback_at_ist': callback.callback_datetime.replace(tzinfo=_tz.utc).astimezone(IST).strftime('%d %b %I:%M %p IST') if getattr(callback, 'callback_datetime', None) else None,
        },
        status='queued',
        scheduled_for=scheduled_for or datetime.utcnow(),
    )
    db.session.add(ev)
    return ev
