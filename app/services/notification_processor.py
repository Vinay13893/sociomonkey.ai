"""
Notification queue processor (Phase M1 delivery).

Drains `NotificationEvent` rows with status='queued', sends Web Push via
`push_dispatcher.send_web_push`, and updates row status:

  queued → sending → sent
                   → failed   (after PUSH_MAX_ATTEMPTS)
                   → skipped  (no active subscription / VAPID not configured)

Called by:
  - /api/cron/drain-notifications  (Vercel Cron, every minute)
  - reminder_scheduler._deliver() for real-time in-process delivery

The function is idempotent: rows being processed concurrently are guarded by
a status='sending' transition before the HTTP call.  On Vercel serverless this
is safe because each invocation runs in its own process.

Back-off schedule (attempts):
  1st attempt → immediate
  2nd attempt → retry only after 5 min  (scheduled_for bumped)
  3rd attempt → retry only after 30 min (scheduled_for bumped)
  4th+ attempt → mark failed, deactivate subscription if action='deactivate'
"""
import logging
from datetime import datetime, timedelta
from time import monotonic

logger = logging.getLogger(__name__)

# Rows per cron run. Keep small to stay within Vercel/serverless limits.
_BATCH_SIZE = 5
_MAX_RUN_SECONDS = 45

_BACKOFF_MINUTES = {1: 5, 2: 30}   # after N-th failure, wait this many minutes


def process_notification_queue(batch_size: int = _BATCH_SIZE) -> dict:
    """
    Drain up to `batch_size` queued notification events.

    Returns a summary dict:
      {sent: N, failed: N, skipped: N, deactivated_subs: N, errors: [str]}
    """
    from flask import current_app
    from app.models.base import db
    from app.models.push import NotificationEvent, PushSubscription
    from app.models.user import User
    from app.services.push_dispatcher import send_web_push

    max_attempts = current_app.config.get('PUSH_MAX_ATTEMPTS', 3)
    vapid_pub = current_app.config.get('VAPID_PUBLIC_KEY', '')
    summary = {'sent': 0, 'failed': 0, 'skipped': 0, 'deactivated_subs': 0, 'recovered': 0, 'errors': []}

    now = datetime.utcnow()
    deadline = monotonic() + _MAX_RUN_SECONDS
    batch_size = max(1, min(int(batch_size or _BATCH_SIZE), 10))

    # A previous serverless timeout can leave rows in "sending". Requeue stale
    # rows so a later cron run can finish delivery instead of losing the event.
    stale_cutoff = now - timedelta(minutes=5)
    recovered = NotificationEvent.query.filter(
        NotificationEvent.status == 'sending',
        db.or_(
            NotificationEvent.claimed_at <= stale_cutoff,
            db.and_(
                NotificationEvent.claimed_at.is_(None),
                NotificationEvent.scheduled_for <= stale_cutoff,
            ),
        ),
    ).update({
        'status': 'queued',
        'claimed_at': None,
        'last_error': 'Recovered from stale sending state',
    }, synchronize_session=False)
    if recovered:
        db.session.commit()
        summary['recovered'] = int(recovered)

    # Fetch queued rows whose scheduled_for is due
    rows = (
        NotificationEvent.query
        .filter(
            NotificationEvent.status == 'queued',
            NotificationEvent.scheduled_for <= now,
        )
        .order_by(NotificationEvent.scheduled_for.asc(), NotificationEvent.id.asc())
        .limit(batch_size)
        .all()
    )

    if not rows:
        return summary

    claimed_ids = []
    for candidate in rows:
        claimed = NotificationEvent.query.filter(
            NotificationEvent.id == candidate.id,
            NotificationEvent.status == 'queued',
        ).update({
            'status': 'sending',
            'claimed_at': now,
        }, synchronize_session=False)
        db.session.commit()
        if claimed == 1:
            claimed_ids.append(candidate.id)

    for event_id in claimed_ids:
        if monotonic() >= deadline:
            event = db.session.get(NotificationEvent, event_id)
            if event and event.status == 'sending':
                event.status = 'queued'
                event.claimed_at = None
                event.last_error = 'Deferred before worker timeout'
                event.scheduled_for = datetime.utcnow() + timedelta(minutes=1)
                db.session.commit()
            summary['errors'].append('worker deadline reached; remaining events deferred')
            break

        # Re-fetch fresh row in case of concurrent update
        event = db.session.get(NotificationEvent, event_id)
        if not event or event.status != 'sending':
            continue

        event.attempts += 1

        # If VAPID not configured, skip — don't waste attempts
        if not vapid_pub:
            event.last_error = 'VAPID_PUBLIC_KEY not set'
            event.claimed_at = None
            if event.attempts < max_attempts:
                event.status = 'queued'
                event.scheduled_for = now + timedelta(minutes=_BACKOFF_MINUTES.get(event.attempts, 60))
            else:
                event.status = 'failed'
                event.dead_lettered_at = datetime.utcnow()
                summary['failed'] += 1
            db.session.commit()
            continue

        # Find active subscriptions for this user
        subs_query = PushSubscription.query.filter_by(user_id=event.user_id, is_active=True)
        if event.tenant_id is not None:
            subs_query = subs_query.filter(PushSubscription.tenant_id == event.tenant_id)
        subs = subs_query.order_by(PushSubscription.id.asc()).all()

        if not subs:
            event.status = 'skipped'
            event.claimed_at = None
            event.last_error = 'No active subscriptions for user'
            db.session.commit()
            summary['skipped'] += 1
            continue

        title   = event.title   or 'Sociomonkey'
        body    = event.body    or ''
        url     = event.deep_link or '/'
        tag     = event.event_type or 'sm-notification'

        any_ok = False
        last_error = ''
        last_action = 'fail'

        for sub in subs:
            if monotonic() >= deadline:
                last_error = 'worker deadline reached before all subscriptions'
                last_action = 'retry'
                break
            result = send_web_push(sub, title, body, url, tag)
            if result.ok:
                any_ok = True
            else:
                last_error = result.error or last_error
                last_action = result.action

                if result.action == 'deactivate':
                    sub.is_active = False
                    sub.updated_at = datetime.utcnow()
                    db.session.commit()
                    summary['deactivated_subs'] += 1
                    logger.info('[NotificationProcessor] Deactivated sub #%d (endpoint expired)', sub.id)

        if any_ok:
            event.status = 'sent'
            event.claimed_at = None
            event.sent_at = datetime.utcnow()
            event.last_error = ''
            db.session.commit()
            summary['sent'] += 1
            logger.debug('[NotificationProcessor] Event #%d sent (%s)', event.id, event.event_type)

        elif event.attempts < max_attempts and last_action == 'retry':
            # Schedule a back-off retry: put back in queue with future scheduled_for
            backoff = _BACKOFF_MINUTES.get(event.attempts, 60)
            event.status = 'queued'
            event.claimed_at = None
            event.scheduled_for = now + timedelta(minutes=backoff)
            event.last_error = last_error[:400] if last_error else ''
            db.session.commit()
            logger.info('[NotificationProcessor] Event #%d retry in %d min (attempt %d)',
                        event.id, backoff, event.attempts)

        else:
            event.status = 'failed'
            event.claimed_at = None
            event.dead_lettered_at = datetime.utcnow()
            event.last_error = last_error[:400] if last_error else 'Max attempts reached'
            db.session.commit()
            summary['failed'] += 1
            logger.warning('[NotificationProcessor] Event #%d failed permanently: %s',
                           event.id, event.last_error)
            summary['errors'].append(f'event#{event.id}: {event.last_error}')

    return summary
