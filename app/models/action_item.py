"""Unified operational Action Items and tenant-facing board configuration."""

from datetime import datetime

from .base import db
from app.utils.time_utils import to_ist_str


class ActionTypeConfiguration(db.Model):
    __tablename__ = 'action_type_configurations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    internal_key = db.Column(db.String(80), nullable=False)
    display_name = db.Column(db.String(160), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    colour = db.Column(db.String(20), nullable=False, default='#2563eb')
    icon = db.Column(db.String(80))
    default_priority_key = db.Column(
        db.String(40), nullable=False, default='NORMAL'
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    visibility = db.Column(db.String(20), nullable=False, default='VISIBLE')
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id', 'internal_key', name='uq_action_type_tenant_key'
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'internal_key': self.internal_key,
            'display_name': self.display_name,
            'display_order': self.display_order,
            'colour': self.colour,
            'icon': self.icon,
            'default_priority_key': self.default_priority_key,
            'is_active': self.is_active,
            'visibility': self.visibility,
        }


class ActionStatusConfiguration(db.Model):
    __tablename__ = 'action_status_configurations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    internal_key = db.Column(db.String(80), nullable=False)
    display_name = db.Column(db.String(160), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    colour = db.Column(db.String(20), nullable=False, default='#64748b')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_terminal = db.Column(db.Boolean, nullable=False, default=False)
    visibility = db.Column(db.String(20), nullable=False, default='VISIBLE')
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id', 'internal_key', name='uq_action_status_tenant_key'
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'internal_key': self.internal_key,
            'display_name': self.display_name,
            'display_order': self.display_order,
            'colour': self.colour,
            'is_active': self.is_active,
            'is_terminal': self.is_terminal,
            'visibility': self.visibility,
        }


class ActionPriorityConfiguration(db.Model):
    __tablename__ = 'action_priority_configurations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    internal_key = db.Column(db.String(40), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    weight = db.Column(db.Integer, nullable=False, default=0)
    colour = db.Column(db.String(20), nullable=False, default='#64748b')
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    visibility = db.Column(db.String(20), nullable=False, default='VISIBLE')
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id', 'internal_key', name='uq_action_priority_tenant_key'
        ),
        db.Index(
            'ix_action_priority_tenant_default',
            'tenant_id', 'is_default', 'is_active',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'internal_key': self.internal_key,
            'display_name': self.display_name,
            'display_order': self.display_order,
            'weight': self.weight,
            'colour': self.colour,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'visibility': self.visibility,
        }


class ActionItem(db.Model):
    """One operational unit of work backed by an existing business entity."""

    __tablename__ = 'action_items'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    source_type = db.Column(db.String(40), nullable=False, index=True)
    source_id = db.Column(db.Integer, index=True)
    action_type_key = db.Column(db.String(80), nullable=False, index=True)
    status_key = db.Column(
        db.String(80), nullable=False, default='PENDING', index=True
    )
    priority_key = db.Column(
        db.String(40), nullable=False, default='NORMAL', index=True
    )
    title = db.Column(db.String(240), nullable=False)
    description = db.Column(db.Text)
    assigned_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), index=True
    )
    assigned_by_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), index=True
    )
    organisation_unit_id = db.Column(
        db.Integer, db.ForeignKey('organisation_units.id'), index=True
    )
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), index=True)
    location_id = db.Column(
        db.Integer, db.ForeignKey('locations.id'), index=True
    )
    due_at = db.Column(db.DateTime, index=True)
    business_rule_priority = db.Column(db.Integer, nullable=False, default=0)
    idempotency_key = db.Column(db.String(300))
    assigned_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
    expired_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    archived_at = db.Column(db.DateTime)
    created_by = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False
    )
    updated_by = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    assigned_user = db.relationship(
        'User', foreign_keys=[assigned_user_id]
    )
    assigned_by_user = db.relationship(
        'User', foreign_keys=[assigned_by_user_id]
    )
    organisation_unit = db.relationship('OrganisationUnit')
    project = db.relationship('Project')
    location = db.relationship('Location')
    creator = db.relationship('User', foreign_keys=[created_by])
    updater = db.relationship('User', foreign_keys=[updated_by])

    __table_args__ = (
        db.CheckConstraint(
            "source_type IN ("
            "'LEAD','VISIT','RECEPTION','CHANNEL_PARTNER','BUSINESS_RULE',"
            "'SLA','CALLBACK','MANUAL','AUTOMATION')",
            name='ck_action_item_source_type',
        ),
        db.Index(
            'ix_action_items_tenant_assignee_status_due',
            'tenant_id', 'assigned_user_id', 'status_key', 'due_at',
        ),
        db.Index(
            'ix_action_items_tenant_source',
            'tenant_id', 'source_type', 'source_id',
        ),
        db.Index(
            'ix_action_items_tenant_unit_status',
            'tenant_id', 'organisation_unit_id', 'status_key',
        ),
        db.Index(
            'uq_action_items_tenant_idempotency',
            'tenant_id', 'idempotency_key', unique=True,
        ),
    )

    @property
    def is_overdue(self):
        return bool(
            self.is_active
            and self.due_at
            and self.status_key not in {'COMPLETED', 'CANCELLED', 'EXPIRED'}
            and self.due_at < datetime.utcnow()
        )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'action_type_key': self.action_type_key,
            'status_key': self.status_key,
            'priority_key': self.priority_key,
            'title': self.title,
            'description': self.description,
            'assigned_user_id': self.assigned_user_id,
            'assigned_user_name': (
                self.assigned_user.name if self.assigned_user else None
            ),
            'assigned_by_user_id': self.assigned_by_user_id,
            'assigned_by_user_name': (
                self.assigned_by_user.name if self.assigned_by_user else None
            ),
            'organisation_unit_id': self.organisation_unit_id,
            'organisation_unit_name': (
                self.organisation_unit.name
                if self.organisation_unit else None
            ),
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'location_id': self.location_id,
            'location_name': self.location.name if self.location else None,
            'due_at': to_ist_str(self.due_at),
            'business_rule_priority': self.business_rule_priority,
            'assigned_at': to_ist_str(self.assigned_at),
            'started_at': to_ist_str(self.started_at),
            'completed_at': to_ist_str(self.completed_at),
            'cancelled_at': to_ist_str(self.cancelled_at),
            'expired_at': to_ist_str(self.expired_at),
            'is_overdue': self.is_overdue,
            'is_active': self.is_active,
            'archived_at': to_ist_str(self.archived_at),
            'created_at': to_ist_str(self.created_at),
            'updated_at': to_ist_str(self.updated_at),
        }
