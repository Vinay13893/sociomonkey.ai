"""In-app and push-queue events for unified Action Items."""

from datetime import datetime

from app.models.base import db
from app.models.notification import Notification
from app.models.push import NotificationEvent
from app.utils.correlation import correlation_id as ensure_correlation_id


EVENTS = {
    'assigned': ('action_assigned', 'Action Assigned'),
    'reassigned': ('action_reassigned', 'Action Reassigned'),
    'due_soon': ('action_due_soon', 'Action Due Soon'),
    'overdue': ('action_overdue', 'Action Overdue'),
    'completed': ('action_completed', 'Action Completed'),
}


def notify_action_item(
    action_item, user, kind, correlation_id=None, idempotency_key=None,
    scheduled_for=None,
):
    """Create the bell record and enqueue the existing push delivery event."""
    if kind not in EVENTS:
        raise ValueError('Unsupported Action Item notification kind')
    event_type, title = EVENTS[kind]
    correlation_id = ensure_correlation_id(correlation_id)
    if idempotency_key:
        existing = NotificationEvent.query.filter_by(
            idempotency_key=idempotency_key
        ).first()
        if existing:
            return existing
    tenant = getattr(user, 'tenant', None)
    slug = getattr(tenant, 'slug', None) or ''
    deep_link = (
        f'/{slug}/action-board?action={action_item.id}' if slug else '/'
    )
    payload = {
        'action_item_id': action_item.id,
        'source_type': action_item.source_type,
        'source_id': action_item.source_id,
        'action_type_key': action_item.action_type_key,
        'status_key': action_item.status_key,
        'priority_key': action_item.priority_key,
        'due_at': (
            action_item.due_at.isoformat() if action_item.due_at else None
        ),
        'correlation_id': correlation_id,
    }
    db.session.add(Notification(
        tenant_id=action_item.tenant_id,
        user_id=user.id,
        category='action_board',
        kind=event_type,
        title=title,
        message=action_item.title,
        payload=payload,
        source='action_items',
        correlation_id=correlation_id,
    ))
    event = NotificationEvent(
        tenant_id=action_item.tenant_id,
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        user_id=user.id,
        event_type=event_type,
        action_item_id=action_item.id,
        origin_type='ACTION_ITEM',
        origin_id=action_item.id,
        lead_id=(
            action_item.source_id
            if action_item.source_type == 'LEAD' else None
        ),
        callback_id=(
            action_item.source_id
            if action_item.source_type == 'CALLBACK' else None
        ),
        channel_partner_id=(
            action_item.source_id
            if action_item.source_type == 'CHANNEL_PARTNER' else None
        ),
        title=title,
        body=action_item.title,
        deep_link=deep_link,
        payload=payload,
        status='queued',
        scheduled_for=scheduled_for or datetime.utcnow(),
    )
    db.session.add(event)
    return event
