"""Immutable lead lifecycle orchestration events."""

from datetime import datetime

from .base import db
from app.utils.time_utils import to_ist_str


class PipelineTransition(db.Model):
    """One append-only movement in a Lead's configured lifecycle."""

    __tablename__ = 'pipeline_transitions'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    lead_id = db.Column(
        db.Integer, db.ForeignKey('leads.id'), nullable=False, index=True
    )
    from_stage_key = db.Column(db.String(80), index=True)
    to_stage_key = db.Column(db.String(80), nullable=False, index=True)
    changed_by_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), index=True
    )
    source = db.Column(db.String(80), nullable=False, default='PIPELINE')
    reason = db.Column(db.Text)
    correlation_id = db.Column(
        db.String(36), nullable=False, index=True
    )
    rule_evaluation = db.Column(db.JSON, nullable=False, default=dict)
    transition_context = db.Column(db.JSON, nullable=False, default=dict)
    previous_owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    current_owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    manager_override = db.Column(db.Boolean, nullable=False, default=False)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), index=True)
    channel_partner_id = db.Column(
        db.Integer, db.ForeignKey('channel_partners.id'), index=True
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    lead = db.relationship('Lead')
    changed_by_user = db.relationship(
        'User', foreign_keys=[changed_by_user_id]
    )
    previous_owner = db.relationship('User', foreign_keys=[previous_owner_id])
    current_owner = db.relationship('User', foreign_keys=[current_owner_id])
    visit = db.relationship('Visit')
    channel_partner = db.relationship('ChannelPartner')

    __table_args__ = (
        db.Index(
            'ix_pipeline_transitions_tenant_stage_created',
            'tenant_id', 'to_stage_key', 'created_at',
        ),
        db.Index(
            'ix_pipeline_transitions_tenant_lead_created',
            'tenant_id', 'lead_id', 'created_at',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'lead_id': self.lead_id,
            'from_stage_key': self.from_stage_key,
            'to_stage_key': self.to_stage_key,
            'changed_by_user_id': self.changed_by_user_id,
            'changed_by_user_name': (
                self.changed_by_user.name if self.changed_by_user else None
            ),
            'source': self.source,
            'reason': self.reason,
            'correlation_id': self.correlation_id,
            'rule_evaluation': self.rule_evaluation or {},
            'previous_owner_id': self.previous_owner_id,
            'current_owner_id': self.current_owner_id,
            'manager_override': self.manager_override,
            'visit_id': self.visit_id,
            'channel_partner_id': self.channel_partner_id,
            'created_at': to_ist_str(self.created_at),
        }
