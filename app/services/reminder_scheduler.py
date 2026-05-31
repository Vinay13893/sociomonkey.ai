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
    lead_name = callback.lead.name if callback.lead else f'Lead #{callback.lead_id}'
    cb_time   = callback.callback_datetime.strftime('%d %b %Y %H:%M')

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


def process_pending_reminders():
    """Public one-shot entry point for cron/worker execution."""
    _process_reminders()


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
