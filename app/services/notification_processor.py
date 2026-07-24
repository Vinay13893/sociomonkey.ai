"""Bounded, idempotent delivery worker for the existing NotificationEvent queue."""

import logging
import threading
from datetime import datetime, timedelta
from time import monotonic
from uuid import uuid4

logger = logging.getLogger(__name__)

_BATCH_SIZE = 5
_MAX_RUN_SECONDS = 45
_BACKOFF_MINUTES = (2, 5, 15, 30, 60)
_WORKER_LOCK = threading.Lock()


def _backoff_minutes(attempt):
    index = max(0, min(int(attempt or 1) - 1, len(_BACKOFF_MINUTES) - 1))
    return _BACKOFF_MINUTES[index]


def _base_summary(worker_run_id):
    return {
        'worker_run_id': worker_run_id,
        'claimed': 0,
        'sent': 0,
        'retrying': 0,
        'failed': 0,
        'skipped': 0,
        'deactivated_subs': 0,
        'recovered': 0,
        'remaining_due': 0,
        'skipped_overlap': False,
        'duration_ms': 0,
        'failure_categories': {},
        'errors': [],
    }


def _bump_failure(summary, category):
    if not category:
        return
    counts = summary['failure_categories']
    counts[category] = int(counts.get(category, 0)) + 1


def process_notification_queue(batch_size=_BATCH_SIZE):
    """Drain a bounded due batch and return a sanitized operational summary."""
    worker_run_id = str(uuid4())
    started = monotonic()
    summary = _base_summary(worker_run_id)
    if not _WORKER_LOCK.acquire(blocking=False):
        summary['skipped_overlap'] = True
        return summary
    try:
        return _process_notification_queue(
            batch_size=batch_size,
            worker_run_id=worker_run_id,
            started=started,
            summary=summary,
        )
    finally:
        summary['duration_ms'] = int((monotonic() - started) * 1000)
        _WORKER_LOCK.release()


def _process_notification_queue(batch_size, worker_run_id, started, summary):
    from flask import current_app

    from app.models.base import db
    from app.models.push import NotificationEvent, PushSubscription
    from app.services.notification_operations import (
        categorise_failure,
        record_attempt,
        sanitise_error,
    )
    from app.services.push_dispatcher import send_web_push

    max_attempts = max(
        1, min(int(current_app.config.get('PUSH_MAX_ATTEMPTS', 3) or 3), 10)
    )
    vapid_pub = current_app.config.get('VAPID_PUBLIC_KEY', '')
    now = datetime.utcnow()
    deadline = started + _MAX_RUN_SECONDS
    batch_size = max(1, min(int(batch_size or _BATCH_SIZE), 10))

    stale_cutoff = now - timedelta(minutes=5)
    stale_rows = (
        NotificationEvent.query
        .filter(
            NotificationEvent.status == 'sending',
            db.or_(
                NotificationEvent.claimed_at <= stale_cutoff,
                db.and_(
                    NotificationEvent.claimed_at.is_(None),
                    NotificationEvent.scheduled_for <= stale_cutoff,
                ),
            ),
        )
        .order_by(NotificationEvent.id.asc())
        .limit(100)
        .all()
    )
    for event in stale_rows:
        event.status = 'queued'
        event.claimed_at = None
        event.last_error = 'Recovered from stale sending state'
        event.failure_category = 'worker_timeout'
        record_attempt(
            event,
            worker_run_id,
            'recovered',
            failure_category='worker_timeout',
            error=event.last_error,
        )
    if stale_rows:
        db.session.commit()
        summary['recovered'] = len(stale_rows)

    rows = (
        NotificationEvent.query
        .filter(
            NotificationEvent.status == 'queued',
            NotificationEvent.scheduled_for <= now,
            NotificationEvent.archived_at.is_(None),
        )
        .order_by(NotificationEvent.scheduled_for.asc(), NotificationEvent.id.asc())
        .limit(batch_size)
        .all()
    )
    claimed_ids = []
    for candidate in rows:
        claimed = NotificationEvent.query.filter(
            NotificationEvent.id == candidate.id,
            NotificationEvent.status == 'queued',
            NotificationEvent.archived_at.is_(None),
        ).update({
            'status': 'sending',
            'claimed_at': now,
        }, synchronize_session=False)
        db.session.commit()
        if claimed == 1:
            claimed_ids.append(candidate.id)
    summary['claimed'] = len(claimed_ids)

    for event_id in claimed_ids:
        if monotonic() >= deadline:
            event = db.session.get(NotificationEvent, event_id)
            if event and event.status == 'sending':
                event.status = 'queued'
                event.claimed_at = None
                event.last_error = 'Deferred before worker timeout'
                event.failure_category = 'worker_timeout'
                event.scheduled_for = datetime.utcnow() + timedelta(minutes=1)
                record_attempt(
                    event,
                    worker_run_id,
                    'retry_scheduled',
                    failure_category='worker_timeout',
                    error=event.last_error,
                    next_retry_at=event.scheduled_for,
                )
                db.session.commit()
                summary['retrying'] += 1
                _bump_failure(summary, 'worker_timeout')
            summary['errors'].append('Worker deadline reached')
            break

        event = db.session.get(NotificationEvent, event_id)
        if not event or event.status != 'sending':
            continue
        event.attempts = int(event.attempts or 0) + 1
        event.last_attempt_at = datetime.utcnow()

        if not vapid_pub:
            category = 'configuration'
            message = 'VAPID public key is not configured'
            _schedule_or_dead_letter(
                event, worker_run_id, max_attempts, category, message,
                summary, record_attempt,
            )
            continue

        subs_query = PushSubscription.query.filter_by(user_id=event.user_id, is_active=True)
        if event.tenant_id is not None:
            subs_query = subs_query.filter(
                PushSubscription.tenant_id == event.tenant_id
            )
        subscriptions = subs_query.order_by(PushSubscription.id.asc()).all()
        if not subscriptions:
            event.status = 'skipped'
            event.claimed_at = None
            event.failure_category = 'no_subscription'
            event.last_error = 'No active subscriptions for user'
            record_attempt(
                event,
                worker_run_id,
                'skipped',
                failure_category='no_subscription',
                error=event.last_error,
            )
            db.session.commit()
            summary['skipped'] += 1
            _bump_failure(summary, 'no_subscription')
            continue

        any_ok = False
        retryable = False
        all_deactivated = True
        last_error = ''
        last_category = None
        for subscription in subscriptions:
            if monotonic() >= deadline:
                retryable = True
                all_deactivated = False
                last_error = 'Worker deadline reached before all subscriptions'
                last_category = 'worker_timeout'
                break
            send_started = monotonic()
            result = send_web_push(
                subscription,
                event.title or 'Sociomonkey',
                event.body or '',
                event.deep_link or '/',
                event.event_type or 'sm-notification',
            )
            duration_ms = int((monotonic() - send_started) * 1000)
            if result.ok:
                any_ok = True
                all_deactivated = False
                subscription.failure_count = 0
                subscription.last_success_at = datetime.utcnow()
                subscription.deactivation_reason = None
                record_attempt(
                    event,
                    worker_run_id,
                    'sent',
                    subscription=subscription,
                    result=result,
                    duration_ms=duration_ms,
                )
                continue

            category = categorise_failure(
                result.action, result.status_code, result.error
            )
            last_error = sanitise_error(result.error)
            last_category = category
            subscription.failure_count = int(subscription.failure_count or 0) + 1
            subscription.last_failure_at = datetime.utcnow()
            retryable = retryable or result.action == 'retry'
            if result.action != 'deactivate':
                all_deactivated = False
            if result.action == 'deactivate':
                subscription.is_active = False
                subscription.deactivated_at = datetime.utcnow()
                subscription.deactivation_reason = category
                summary['deactivated_subs'] += 1
            record_attempt(
                event,
                worker_run_id,
                'subscription_failed',
                subscription=subscription,
                result=result,
                failure_category=category,
                duration_ms=duration_ms,
            )
            _bump_failure(summary, category)

        if any_ok:
            event.status = 'sent'
            event.claimed_at = None
            event.sent_at = datetime.utcnow()
            event.last_error = None
            event.failure_category = None
            event.dead_lettered_at = None
            db.session.commit()
            summary['sent'] += 1
        elif all_deactivated:
            event.status = 'skipped'
            event.claimed_at = None
            event.failure_category = last_category or 'expired_subscription'
            event.last_error = last_error or 'All subscriptions expired'
            record_attempt(
                event,
                worker_run_id,
                'skipped',
                failure_category=event.failure_category,
                error=event.last_error,
            )
            db.session.commit()
            summary['skipped'] += 1
        elif retryable and event.attempts < max_attempts:
            event.status = 'queued'
            event.claimed_at = None
            event.failure_category = last_category or 'provider_transient'
            event.last_error = last_error or 'Provider delivery failed'
            event.scheduled_for = datetime.utcnow() + timedelta(
                minutes=_backoff_minutes(event.attempts)
            )
            record_attempt(
                event,
                worker_run_id,
                'retry_scheduled',
                failure_category=event.failure_category,
                error=event.last_error,
                next_retry_at=event.scheduled_for,
            )
            db.session.commit()
            summary['retrying'] += 1
        else:
            event.status = 'failed'
            event.claimed_at = None
            event.failure_category = last_category or 'provider_rejected'
            event.last_error = last_error or 'Maximum attempts reached'
            event.dead_lettered_at = datetime.utcnow()
            record_attempt(
                event,
                worker_run_id,
                'dead_lettered',
                failure_category=event.failure_category,
                error=event.last_error,
            )
            db.session.commit()
            summary['failed'] += 1
            summary['errors'].append(
                f'Event {event.id}: {sanitise_error(event.last_error)}'
            )

    summary['remaining_due'] = NotificationEvent.query.filter(
        NotificationEvent.status == 'queued',
        NotificationEvent.scheduled_for <= datetime.utcnow(),
        NotificationEvent.archived_at.is_(None),
    ).count()
    summary['errors'] = summary['errors'][:20]
    summary['duration_ms'] = int((monotonic() - started) * 1000)
    return summary


def _schedule_or_dead_letter(
    event,
    worker_run_id,
    max_attempts,
    category,
    message,
    summary,
    record_attempt,
):
    from app.models.base import db

    event.claimed_at = None
    event.failure_category = category
    event.last_error = message
    _bump_failure(summary, category)
    if event.attempts < max_attempts:
        event.status = 'queued'
        event.scheduled_for = datetime.utcnow() + timedelta(
            minutes=_backoff_minutes(event.attempts)
        )
        record_attempt(
            event,
            worker_run_id,
            'retry_scheduled',
            failure_category=category,
            error=message,
            next_retry_at=event.scheduled_for,
        )
        summary['retrying'] += 1
    else:
        event.status = 'failed'
        event.dead_lettered_at = datetime.utcnow()
        record_attempt(
            event,
            worker_run_id,
            'dead_lettered',
            failure_category=category,
            error=message,
        )
        summary['failed'] += 1
    db.session.commit()
