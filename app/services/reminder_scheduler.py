"""
Callback Reminder Scheduler
============================
Runs as a background daemon thread that wakes every 60 seconds and
processes pending CallbackReminder rows.

Reminder rules
--------------
1. 10-minute warning  → fires when callback_datetime is ≤ 10 min away
                        and reminder_10_sent is False
2. Due notification   → fires when callback_datetime has passed (≤ 5 min ago)
                        and reminder_due_sent is False

Delivery (Phase 1: in-app notifications only)
---------------------------------------------
Reminders are written to a server-side in-memory queue per tenant user.
The frontend polls /api/leads/notifications every 30 s to drain the queue.

Architecture is delivery-provider agnostic: swap _deliver() to add email
/ WhatsApp / push-notification providers later.
"""
import logging
import os
import threading
from datetime import datetime, timedelta

from app.models.base import db
from app.models.lead import CallbackReminder
from app.models.notification import Notification

logger = logging.getLogger(__name__)
_REMINDER_LOCK = threading.Lock()
_REMINDER_BATCH_SIZE = 100


def push_notification(user_id: int, notification: dict):
    note = Notification(
        tenant_id=notification.get('tenant_id'),
        user_id=user_id,
        category=notification.get('type') or notification.get('category') or 'system',
        kind=notification.get('kind') or 'info',
        title=notification.get('title'),
        message=notification.get('message') or '',
        payload=notification,
        source=notification.get('source') or 'callback_scheduler',
    )
    db.session.add(note)
    db.session.commit()


def drain_notifications(user_id: int) -> list:
    """Return unread notifications for a user and mark them read."""
    rows = (
        Notification.query
        .filter_by(user_id=user_id, is_read=False)
        .order_by(Notification.created_at.asc())
        .all()
    )
    if not rows:
        return []

    now = datetime.utcnow()
    payloads = []
    for row in rows:
        row.is_read = True
        row.read_at = now
        payloads.append(row.to_dict())
    db.session.commit()
    return payloads


# ---------------------------------------------------------------------------
# Internal delivery helper
# ---------------------------------------------------------------------------

def _deliver(callback: 'CallbackReminder', kind: str):
    """
    Send an in-app notification.
    `kind` is '10min' or 'due'.
    """
    from app.utils.time_utils import IST
    lead_name = callback.lead.name if callback.lead else f'Lead #{callback.lead_id}'
    # Display callback time in IST (Gurgaon timezone)
    cb_dt_ist = callback.callback_datetime.replace(tzinfo=__import__('datetime').timezone.utc).astimezone(IST)
    cb_time   = cb_dt_ist.strftime('%d %b %Y %I:%M %p IST')

    if kind == '10min':
        title = 'Upcoming Callback'
        msg = f'🔔 Reminder: Callback for {lead_name} in 10 minutes ({cb_time})'
    else:
        title = 'Callback Due Now'
        msg = f'⏰ Callback due NOW: {lead_name} ({cb_time})'

    note = {'type': 'callback', 'kind': kind, 'title': title, 'lead_id': callback.lead_id,
            'lead_name': lead_name, 'callback_id': callback.id,
            'message': msg, 'ts': datetime.utcnow().isoformat()}
    note['tenant_id'] = callback.tenant_id

    recipients = set()
    if callback.assigned_user_id:
        recipients.add(callback.assigned_user_id)
    if callback.manager_id:
        recipients.add(callback.manager_id)

    for uid in recipients:
        push_notification(uid, dict(note))

    # Phase M1: also enqueue NotificationEvent rows so a future push worker
    # can deliver the same event off-tab via Web Push / FCM. Best-effort —
    # any failure here must NOT break in-app delivery above.
    try:
        from app.models.user import User
        from app.services.notification_events import enqueue_callback_event
        from app.models.base import db as _db
        event_kind = 'due_soon' if kind == '10min' else 'due_now'
        for uid in recipients:
            recipient = User.query.get(uid)
            if recipient:
                enqueue_callback_event(recipient, callback, event_kind)
        _db.session.commit()
    except Exception:
        try:
            from app.models.base import db as _db
            _db.session.rollback()
        except Exception:
            pass

    logger.info('[ReminderScheduler] %s notification sent for callback #%d to users %s',
                kind, callback.id, recipients)


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------

def _run_scheduler(app):
    """Background thread: poll every 60 s, fire due reminders."""
    with app.app_context():
        while True:
            try:
                _process_reminders()
            except Exception as exc:
                logger.exception('[ReminderScheduler] Unexpected error: %s', exc)
            threading.Event().wait(60)   # sleep 60 s


def _process_reminders_unlocked(batch_size: int = _REMINDER_BATCH_SIZE):
    from sqlalchemy.orm import joinedload

    batch_size = max(1, min(int(batch_size or _REMINDER_BATCH_SIZE), 500))
    now = datetime.utcnow()
    ten_min_from_now = now + timedelta(minutes=10)
    one_min_from_now = now + timedelta(minutes=1)

    # 10-minute warning (exclude the last 1 minute — those will fire as "due" instead)
    due_10 = CallbackReminder.query.options(joinedload(CallbackReminder.lead)).filter(
        CallbackReminder.status == 'pending',
        CallbackReminder.reminder_10_sent == False,   # noqa: E712
        CallbackReminder.callback_datetime <= ten_min_from_now,
        CallbackReminder.callback_datetime > one_min_from_now,
    ).order_by(
        CallbackReminder.callback_datetime.asc(),
        CallbackReminder.id.asc(),
    ).limit(batch_size).all()

    for cb in due_10:
        _deliver(cb, '10min')
        cb.reminder_10_sent = True

    # Due notification — fire 1 minute early so push arrives by scheduled time
    remaining = max(1, batch_size - len(due_10))
    due_now = CallbackReminder.query.options(joinedload(CallbackReminder.lead)).filter(
        CallbackReminder.status == 'pending',
        CallbackReminder.reminder_due_sent == False,  # noqa: E712
        CallbackReminder.callback_datetime <= one_min_from_now,
    ).order_by(
        CallbackReminder.callback_datetime.asc(),
        CallbackReminder.id.asc(),
    ).limit(remaining).all()

    for cb in due_now:
        _deliver(cb, 'due')
        cb.reminder_due_sent = True
        # Auto-mark as missed if no explicit completion after 6 hours
        # (a separate cleanup job could do this; leaving pending allows manual completion)

    if due_10 or due_now:
        db.session.commit()
    return {'processed_10min': len(due_10), 'processed_due': len(due_now), 'skipped_overlap': False}


def _process_reminders(batch_size: int = _REMINDER_BATCH_SIZE):
    if not _REMINDER_LOCK.acquire(blocking=False):
        logger.info('[ReminderScheduler] Skip overlapping reminder run.')
        return {'processed_10min': 0, 'processed_due': 0, 'skipped_overlap': True}
    try:
        return _process_reminders_unlocked(batch_size=batch_size)
    finally:
        _REMINDER_LOCK.release()


def process_pending_reminders(batch_size: int = _REMINDER_BATCH_SIZE):
    """Public one-shot entry point for cron/worker execution."""
    return _process_reminders(batch_size=batch_size)


# ---------------------------------------------------------------------------
# Start the scheduler once per process
# ---------------------------------------------------------------------------

def start_scheduler(app):
    # Backward-compatible hook retained for Railway, but notifications now persist in DB.
    if threading is None:
        return
    if app.config.get('ENV') == 'production' and (app.config.get('VERCEL') or os.environ.get('VERCEL')):
        return
    if getattr(app, '_scheduler_started', False):
        return
    app._scheduler_started = True

    t = threading.Thread(
        target=_run_scheduler,
        args=(app,),
        daemon=True,
        name='ReminderScheduler',
    )
    t.start()
    logger.info('[ReminderScheduler] Started.')
