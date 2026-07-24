"""Tenant-scoped notification queue diagnostics and operator actions."""

from datetime import datetime, timedelta

from app.models.activity import ActivityLog
from app.models.base import db
from app.models.lead import CallbackReminder
from app.models.push import (
    NotificationDeliveryAttempt,
    NotificationEvent,
    PushSubscription,
)
from app.utils.correlation import correlation_id


REPLAYABLE_STATUSES = {'failed', 'skipped'}
ARCHIVABLE_STATUSES = {'sent', 'skipped'}


def sanitise_error(value):
    """Return a bounded operational error without endpoints or credentials."""
    text = ' '.join(str(value or '').split())
    for marker in ('https://', 'http://'):
        if marker in text:
            text = text.split(marker, 1)[0].strip() or 'Provider request failed'
    return text[:400]


def categorise_failure(action=None, status_code=None, error=None):
    action = str(action or '').lower()
    message = str(error or '').lower()
    code = int(status_code or 0)
    if action == 'deactivate' or code in (404, 410):
        return 'expired_subscription'
    if code == 429:
        return 'rate_limited'
    if code >= 500 or action == 'retry':
        return 'provider_transient'
    if code == 401 or 'vapid' in message:
        return 'configuration'
    if code == 413 or 'payload' in message:
        return 'payload_invalid'
    if code == 400 or 'missing endpoint' in message or 'missing endpoint/keys' in message:
        return 'subscription_invalid'
    if 'no active subscription' in message:
        return 'no_subscription'
    if 'timeout' in message or 'deadline' in message:
        return 'worker_timeout'
    return 'provider_rejected'


def record_attempt(
    event,
    worker_run_id,
    outcome,
    subscription=None,
    result=None,
    failure_category=None,
    error=None,
    duration_ms=None,
    next_retry_at=None,
):
    """Append one immutable delivery history row to the current transaction."""
    status_code = getattr(result, 'status_code', None)
    action = getattr(result, 'action', None)
    result_error = getattr(result, 'error', None)
    category = failure_category
    if not category and outcome not in ('sent', 'manual_replay', 'recovered'):
        category = categorise_failure(action, status_code, result_error or error)
    row = NotificationDeliveryAttempt(
        tenant_id=event.tenant_id,
        notification_event_id=event.id,
        push_subscription_id=getattr(subscription, 'id', None),
        correlation_id=event.correlation_id,
        worker_run_id=worker_run_id,
        attempt_number=max(0, int(event.attempts or 0)),
        outcome=outcome,
        failure_category=category,
        provider_status=status_code,
        error_summary=sanitise_error(result_error or error),
        duration_ms=duration_ms,
        next_retry_at=next_retry_at,
    )
    db.session.add(row)
    return row


def _age_seconds(value, now=None):
    if not value:
        return None
    now = now or datetime.utcnow()
    return max(0, int((now - value).total_seconds()))


def queue_health(tenant_id):
    """Return aggregate queue, subscription, and reminder health."""
    now = datetime.utcnow()
    status_rows = (
        db.session.query(NotificationEvent.status, db.func.count(NotificationEvent.id))
        .filter(
            NotificationEvent.tenant_id == tenant_id,
            NotificationEvent.archived_at.is_(None),
        )
        .group_by(NotificationEvent.status)
        .all()
    )
    event_counts = {str(status): int(count) for status, count in status_rows}
    oldest_pending = (
        db.session.query(db.func.min(NotificationEvent.created_at))
        .filter(
            NotificationEvent.tenant_id == tenant_id,
            NotificationEvent.status == 'queued',
            NotificationEvent.archived_at.is_(None),
        )
        .scalar()
    )
    due_pending = NotificationEvent.query.filter(
        NotificationEvent.tenant_id == tenant_id,
        NotificationEvent.status == 'queued',
        NotificationEvent.scheduled_for <= now,
        NotificationEvent.archived_at.is_(None),
    ).count()
    scheduled_retry = NotificationEvent.query.filter(
        NotificationEvent.tenant_id == tenant_id,
        NotificationEvent.status == 'queued',
        NotificationEvent.scheduled_for > now,
        NotificationEvent.attempts > 0,
        NotificationEvent.archived_at.is_(None),
    ).count()
    failure_rows = (
        db.session.query(
            NotificationEvent.failure_category,
            db.func.count(NotificationEvent.id),
        )
        .filter(
            NotificationEvent.tenant_id == tenant_id,
            NotificationEvent.failure_category.isnot(None),
            NotificationEvent.status.in_(('queued', 'failed', 'skipped')),
            NotificationEvent.archived_at.is_(None),
        )
        .group_by(NotificationEvent.failure_category)
        .all()
    )
    subscription_rows = (
        db.session.query(
            PushSubscription.is_active,
            db.func.count(PushSubscription.id),
        )
        .filter(PushSubscription.tenant_id == tenant_id)
        .group_by(PushSubscription.is_active)
        .all()
    )
    subscriptions = {'active': 0, 'inactive': 0}
    for active, count in subscription_rows:
        subscriptions['active' if active else 'inactive'] = int(count)
    subscriptions['expired'] = PushSubscription.query.filter(
        PushSubscription.tenant_id == tenant_id,
        PushSubscription.deactivation_reason == 'expired_subscription',
    ).count()
    attempt_count = NotificationDeliveryAttempt.query.filter(
        NotificationDeliveryAttempt.tenant_id == tenant_id,
        NotificationDeliveryAttempt.created_at >= now - timedelta(days=7),
    ).count()
    retry_count = NotificationDeliveryAttempt.query.filter(
        NotificationDeliveryAttempt.tenant_id == tenant_id,
        NotificationDeliveryAttempt.outcome == 'retry_scheduled',
        NotificationDeliveryAttempt.created_at >= now - timedelta(days=7),
    ).count()
    sent_timestamps = (
        db.session.query(NotificationEvent.created_at, NotificationEvent.sent_at)
        .filter(
            NotificationEvent.tenant_id == tenant_id,
            NotificationEvent.status == 'sent',
            NotificationEvent.sent_at.isnot(None),
            NotificationEvent.created_at >= now - timedelta(days=7),
        )
        .order_by(NotificationEvent.sent_at.desc())
        .limit(1000)
        .all()
    )
    sent_latencies = [
        max(0, (sent_at - created_at).total_seconds())
        for created_at, sent_at in sent_timestamps
        if created_at and sent_at
    ]
    reminder_base = CallbackReminder.query.filter(
        CallbackReminder.tenant_id == tenant_id,
        CallbackReminder.status == 'pending',
    )
    overdue_reminder = (
        reminder_base.filter(CallbackReminder.callback_datetime <= now)
        .order_by(CallbackReminder.callback_datetime.asc())
        .first()
    )
    return {
        'generated_at': now.isoformat(),
        'queue': {
            'counts': event_counts,
            'depth': sum(
                event_counts.get(status, 0)
                for status in ('queued', 'sending', 'failed')
            ),
            'due_pending': int(due_pending),
            'scheduled_retry': int(scheduled_retry),
            'dead_letter': int(event_counts.get('failed', 0)),
            'oldest_pending_at': (
                oldest_pending.isoformat() if oldest_pending else None
            ),
            'oldest_pending_age_seconds': _age_seconds(oldest_pending, now),
            'failure_categories': {
                str(category): int(count)
                for category, count in failure_rows
            },
        },
        'delivery': {
            'attempts_7d': int(attempt_count),
            'retries_7d': int(retry_count),
            'average_latency_seconds_7d': (
                round(sum(sent_latencies) / len(sent_latencies), 2)
                if sent_latencies else None
            ),
        },
        'subscriptions': subscriptions,
        'reminders': {
            'pending_future': reminder_base.filter(
                CallbackReminder.callback_datetime > now
            ).count(),
            'due_or_overdue': reminder_base.filter(
                CallbackReminder.callback_datetime <= now
            ).count(),
            'oldest_overdue_at': (
                overdue_reminder.callback_datetime.isoformat()
                if overdue_reminder else None
            ),
            'oldest_overdue_age_seconds': (
                _age_seconds(overdue_reminder.callback_datetime, now)
                if overdue_reminder else None
            ),
        },
    }


def list_events(tenant_id, args):
    page = max(1, int(args.get('page', 1) or 1))
    per_page = max(1, min(int(args.get('per_page', 25) or 25), 100))
    query = NotificationEvent.query.filter(
        NotificationEvent.tenant_id == tenant_id,
        NotificationEvent.archived_at.is_(None),
    )
    status = str(args.get('status') or '').strip().lower()
    event_type = str(args.get('event_type') or '').strip()
    category = str(args.get('failure_category') or '').strip()
    search = str(args.get('search') or '').strip()
    if status:
        query = query.filter(NotificationEvent.status == status)
    if event_type:
        query = query.filter(NotificationEvent.event_type == event_type)
    if category:
        query = query.filter(NotificationEvent.failure_category == category)
    if search:
        terms = [NotificationEvent.correlation_id.ilike(f'%{search}%')]
        if search.isdigit():
            terms.append(NotificationEvent.id == int(search))
        query = query.filter(db.or_(*terms))
    total = query.count()
    rows = (
        query.order_by(NotificationEvent.created_at.desc(), NotificationEvent.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        'events': [_event_summary(row) for row in rows],
        'page': page,
        'per_page': per_page,
        'total': int(total),
        'pages': max(1, (int(total) + per_page - 1) // per_page),
    }


def _event_summary(event):
    return {
        'id': event.id,
        'event_type': event.event_type,
        'status': event.status,
        'attempts': event.attempts,
        'failure_category': event.failure_category,
        'correlation_id': event.correlation_id,
        'origin_type': event.origin_type,
        'origin_id': event.origin_id,
        'scheduled_for': (
            event.scheduled_for.isoformat() if event.scheduled_for else None
        ),
        'sent_at': event.sent_at.isoformat() if event.sent_at else None,
        'dead_lettered_at': (
            event.dead_lettered_at.isoformat()
            if event.dead_lettered_at else None
        ),
        'created_at': event.created_at.isoformat() if event.created_at else None,
        'replay_count': event.replay_count,
    }


def event_detail(tenant_id, event_id):
    event = NotificationEvent.query.filter_by(
        tenant_id=tenant_id,
        id=event_id,
    ).first()
    if not event:
        return None
    attempts = (
        NotificationDeliveryAttempt.query
        .filter_by(tenant_id=tenant_id, notification_event_id=event.id)
        .order_by(NotificationDeliveryAttempt.id.desc())
        .limit(100)
        .all()
    )
    result = _event_summary(event)
    result['last_error'] = sanitise_error(event.last_error)
    result['attempt_history'] = [row.to_dict() for row in attempts]
    return result


def replay_event(event, actor, requested_correlation_id=None):
    if event.status not in REPLAYABLE_STATUSES:
        raise ValueError('Only failed or skipped events can be replayed')
    previous = _event_summary(event)
    now = datetime.utcnow()
    operation_correlation = correlation_id(
        requested_correlation_id or event.correlation_id
    )
    event.status = 'queued'
    event.attempts = 0
    event.last_error = None
    event.failure_category = None
    event.scheduled_for = now
    event.claimed_at = None
    event.dead_lettered_at = None
    event.archived_at = None
    event.replay_count = int(event.replay_count or 0) + 1
    event.replayed_at = now
    event.correlation_id = event.correlation_id or operation_correlation
    record_attempt(
        event,
        operation_correlation,
        'manual_replay',
    )
    db.session.add(ActivityLog(
        tenant_id=event.tenant_id,
        user_id=actor.id,
        action='REPLAY',
        module='notifications',
        resource_id=event.id,
        resource_type='notification_event',
        old_value=previous,
        new_value=_event_summary(event),
        description='Notification delivery event requeued',
        correlation_id=operation_correlation,
    ))
    db.session.commit()
    return _event_summary(event)


def archive_completed(tenant_id, actor, older_than_days=30, limit=500,
                      requested_correlation_id=None):
    cutoff = datetime.utcnow() - timedelta(
        days=max(1, min(int(older_than_days or 30), 365))
    )
    limit = max(1, min(int(limit or 500), 500))
    rows = (
        NotificationEvent.query
        .filter(
            NotificationEvent.tenant_id == tenant_id,
            NotificationEvent.status.in_(ARCHIVABLE_STATUSES),
            NotificationEvent.archived_at.is_(None),
            NotificationEvent.created_at < cutoff,
        )
        .order_by(NotificationEvent.id.asc())
        .limit(limit)
        .all()
    )
    now = datetime.utcnow()
    ids = []
    for row in rows:
        row.archived_at = now
        ids.append(row.id)
    operation_correlation = correlation_id(requested_correlation_id)
    if ids:
        db.session.add(ActivityLog(
            tenant_id=tenant_id,
            user_id=actor.id,
            action='ARCHIVE',
            module='notifications',
            resource_type='notification_event',
            old_value={'archived': False},
            new_value={'archived': True, 'count': len(ids)},
            description='Completed notification delivery events archived',
            correlation_id=operation_correlation,
        ))
    db.session.commit()
    return {
        'archived': len(ids),
        'correlation_id': operation_correlation,
    }
