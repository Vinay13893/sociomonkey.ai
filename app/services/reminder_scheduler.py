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
import threading
import logging
from datetime import datetime, timedelta

from app.models.base import db
from app.models.lead import CallbackReminder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-app notification store  {user_id: [notification_dict, ...]}
# ---------------------------------------------------------------------------
_notification_store: dict[int, list] = {}
_store_lock = threading.Lock()

_scheduler_started = False
_scheduler_lock = threading.Lock()


def push_notification(user_id: int, notification: dict):
    with _store_lock:
        if user_id not in _notification_store:
            _notification_store[user_id] = []
        _notification_store[user_id].append(notification)
        # Keep at most 50 notifications per user to avoid unbounded growth
        _notification_store[user_id] = _notification_store[user_id][-50:]


def drain_notifications(user_id: int) -> list:
    """Return and clear pending notifications for a user."""
    with _store_lock:
        msgs = _notification_store.pop(user_id, [])
    return msgs


# ---------------------------------------------------------------------------
# Internal delivery helper
# ---------------------------------------------------------------------------

def _deliver(callback: 'CallbackReminder', kind: str):
    """
    Send an in-app notification.
    `kind` is '10min' or 'due'.
    """
    lead_name = callback.lead.name if callback.lead else f'Lead #{callback.lead_id}'
    cb_time   = callback.callback_datetime.strftime('%d %b %Y %H:%M')

    if kind == '10min':
        msg = f'🔔 Reminder: Callback for {lead_name} in 10 minutes ({cb_time})'
    else:
        msg = f'⏰ Callback due NOW: {lead_name} ({cb_time})'

    note = {'type': 'callback', 'kind': kind, 'lead_id': callback.lead_id,
            'lead_name': lead_name, 'callback_id': callback.id,
            'message': msg, 'ts': datetime.utcnow().isoformat()}

    recipients = set()
    if callback.assigned_user_id:
        recipients.add(callback.assigned_user_id)
    if callback.manager_id:
        recipients.add(callback.manager_id)

    for uid in recipients:
        push_notification(uid, dict(note))

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


def _process_reminders():
    now = datetime.utcnow()
    ten_min_from_now = now + timedelta(minutes=10)
    grace_window = now - timedelta(minutes=5)   # don't fire "due" reminders older than 5 min

    # 10-minute warning
    due_10 = CallbackReminder.query.filter(
        CallbackReminder.status == 'pending',
        CallbackReminder.reminder_10_sent == False,   # noqa: E712
        CallbackReminder.callback_datetime <= ten_min_from_now,
        CallbackReminder.callback_datetime > now,
    ).all()

    for cb in due_10:
        _deliver(cb, '10min')
        cb.reminder_10_sent = True

    # Due notification
    due_now = CallbackReminder.query.filter(
        CallbackReminder.status == 'pending',
        CallbackReminder.reminder_due_sent == False,  # noqa: E712
        CallbackReminder.callback_datetime <= now,
        CallbackReminder.callback_datetime >= grace_window,
    ).all()

    for cb in due_now:
        _deliver(cb, 'due')
        cb.reminder_due_sent = True
        # Auto-mark as missed if no explicit completion after 6 hours
        # (a separate cleanup job could do this; leaving pending allows manual completion)

    if due_10 or due_now:
        db.session.commit()


# ---------------------------------------------------------------------------
# Start the scheduler once per process
# ---------------------------------------------------------------------------

def start_scheduler(app):
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    t = threading.Thread(
        target=_run_scheduler,
        args=(app,),
        daemon=True,
        name='ReminderScheduler',
    )
    t.start()
    logger.info('[ReminderScheduler] Started.')
