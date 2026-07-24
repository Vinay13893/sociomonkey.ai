"""
Push notification subscription + outbound event queue (Phase M1 foundation).

PushSubscription
----------------
Stores one row per (user, device) endpoint. Tenant-scoped so we can route
broadcasts per tenant later. Compatible with both Web Push (endpoint + keys)
and future FCM HTTP v1 (registration_token in `endpoint`).

NotificationEvent
-----------------
Outbound event queue. The application enqueues events (lead assigned, callback
due, etc); a worker (Vercel Cron) will later drain this queue and send pushes
via the registered subscriptions. No delivery happens in Phase M1.
"""
from datetime import datetime

from .base import db


class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.Text, nullable=True)
    auth = db.Column(db.Text, nullable=True)
    platform = db.Column(db.String(20), nullable=True)  # ios | android | web
    user_agent = db.Column(db.String(400), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'endpoint', name='uq_push_subscriptions_user_endpoint'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tenant_id': self.tenant_id,
            'platform': self.platform,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class NotificationEvent(db.Model):
    """
    Outbound event queue. Enqueued by application code; drained by a worker.
    Phase M1: enqueue only. Delivery wired in a later phase.

    event_type values:
      - lead_assigned
      - lead_reassigned
      - callback_due_soon   (10 minutes before)
      - callback_due_now
      - callback_overdue
      - visit_assigned
      - channel_partner_assigned
      - channel_partner_visit_arrival
      - channel_partner_visit_completed
      - channel_partner_profile_changed
      - action_assigned
      - action_reassigned
      - action_due_soon
      - action_overdue
      - action_completed
    """
    __tablename__ = 'notification_events'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    correlation_id = db.Column(db.String(36), nullable=True, index=True)
    idempotency_key = db.Column(db.String(300), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=True, index=True)
    channel_partner_id = db.Column(
        db.Integer, db.ForeignKey('channel_partners.id'), nullable=True, index=True
    )
    action_item_id = db.Column(
        db.Integer, db.ForeignKey('action_items.id'), nullable=True, index=True
    )
    pipeline_transition_id = db.Column(
        db.Integer, db.ForeignKey('pipeline_transitions.id'),
        nullable=True, index=True,
    )
    callback_id = db.Column(db.Integer, db.ForeignKey('callback_reminders.id'), nullable=True)
    title = db.Column(db.String(200), nullable=True)
    body = db.Column(db.String(400), nullable=True)
    deep_link = db.Column(db.String(400), nullable=True)
    payload = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), default='queued', nullable=False, index=True)  # queued|sent|failed|skipped
    attempts = db.Column(db.Integer, default=0, nullable=False)
    last_error = db.Column(db.String(400), nullable=True)
    scheduled_for = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    claimed_at = db.Column(db.DateTime, nullable=True, index=True)
    dead_lettered_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index('uq_notification_event_idempotency_key', 'idempotency_key', unique=True),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'correlation_id': self.correlation_id,
            'user_id': self.user_id,
            'event_type': self.event_type,
            'lead_id': self.lead_id,
            'channel_partner_id': self.channel_partner_id,
            'action_item_id': self.action_item_id,
            'pipeline_transition_id': self.pipeline_transition_id,
            'callback_id': self.callback_id,
            'title': self.title,
            'body': self.body,
            'deep_link': self.deep_link,
            'status': self.status,
            'attempts': self.attempts,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
