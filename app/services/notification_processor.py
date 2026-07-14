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

logger = logging.getLogger(__name__)

# Rows per cron run. Keep small to stay within Vercel's 10s function limit.
_BATCH_SIZE = 50

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
    summary = {'sent': 0, 'failed': 0, 'skipped': 0, 'deactivated_subs': 0, 'errors': []}

    now = datetime.utcnow()

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

    # Mark as sending atomically before dispatch (prevents double-send)
    row_ids = [r.id for r in rows]
    NotificationEvent.query.filter(
        NotificationEvent.id.in_(row_ids),
        NotificationEvent.status == 'queued',
    ).update({'status': 'sending'}, synchronize_session='fetch')
    db.session.commit()

    for event in rows:
        # Re-fetch fresh row in case of concurrent update
        event = db.session.get(NotificationEvent, event.id)
        if not event or event.status not in ('sending', 'queued'):
            continue

        event.attempts += 1

        # If VAPID not configured, skip — don't waste attempts
        if not vapid_pub:
            event.status = 'skipped'
            event.last_error = 'VAPID_PUBLIC_KEY not set'
            db.session.commit()
            summary['skipped'] += 1
            continue

        # Find active subscriptions for this user
        subs_query = PushSubscription.query.filter_by(user_id=event.user_id, is_active=True)
        if event.tenant_id is not None:
            subs_query = subs_query.filter(PushSubscription.tenant_id == event.tenant_id)
        subs = subs_query.order_by(PushSubscription.id.asc()).all()

        if not subs:
            event.status = 'skipped'
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
            event.sent_at = datetime.utcnow()
            event.last_error = ''
            db.session.commit()
            summary['sent'] += 1
            logger.debug('[NotificationProcessor] Event #%d sent (%s)', event.id, event.event_type)

        elif event.attempts < max_attempts and last_action == 'retry':
            # Schedule a back-off retry: put back in queue with future scheduled_for
            backoff = _BACKOFF_MINUTES.get(event.attempts, 60)
            event.status = 'queued'
            event.scheduled_for = now + timedelta(minutes=backoff)
            event.last_error = last_error[:400] if last_error else ''
            db.session.commit()
            logger.info('[NotificationProcessor] Event #%d retry in %d min (attempt %d)',
                        event.id, backoff, event.attempts)

        else:
            event.status = 'failed'
            event.last_error = last_error[:400] if last_error else 'Max attempts reached'
            db.session.commit()
            summary['failed'] += 1
            logger.warning('[NotificationProcessor] Event #%d failed permanently: %s',
                           event.id, event.last_error)
            summary['errors'].append(f'event#{event.id}: {event.last_error}')

    return summary
