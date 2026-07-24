"""Tenant-configurable display metadata and operational rules."""

from datetime import datetime

from .base import db


class LeadStatusConfiguration(db.Model):
    __tablename__ = 'lead_status_configurations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    internal_key = db.Column(db.String(80), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    colour = db.Column(db.String(20), nullable=False, default='#64748b')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    pipeline_group = db.Column(db.String(80))
    is_qualified = db.Column(db.Boolean, nullable=False, default=False)
    is_lost = db.Column(db.Boolean, nullable=False, default=False)
    is_terminal = db.Column(db.Boolean, nullable=False, default=False)
    is_success = db.Column(db.Boolean, nullable=False, default=False)
    entry_rule_keys = db.Column(db.JSON, nullable=False, default=list)
    exit_rule_keys = db.Column(db.JSON, nullable=False, default=list)
    required_action_type_keys = db.Column(db.JSON, nullable=False, default=list)
    default_actions = db.Column(db.JSON, nullable=False, default=list)
    visibility = db.Column(db.String(20), nullable=False, default='VISIBLE')
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'internal_key', name='uq_status_config_tenant_key'),
    )

    def to_dict(self):
        return {key: getattr(self, key) for key in (
            'id', 'tenant_id', 'internal_key', 'display_name', 'display_order',
            'colour', 'is_active', 'pipeline_group', 'is_qualified', 'is_lost',
            'is_terminal', 'is_success', 'entry_rule_keys', 'exit_rule_keys',
            'required_action_type_keys', 'default_actions', 'visibility',
        )}


class LeadSourceConfiguration(db.Model):
    __tablename__ = 'lead_source_configurations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    lead_source_id = db.Column(db.Integer, db.ForeignKey('lead_sources.id'), nullable=False, index=True)
    display_name = db.Column(db.String(200), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    reporting_group = db.Column(db.String(120))
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'))
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    visibility = db.Column(db.String(20), nullable=False, default='VISIBLE')
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    source = db.relationship('LeadSource')
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'lead_source_id', name='uq_source_config_tenant_source'),
    )

    def to_dict(self):
        return {key: getattr(self, key) for key in (
            'id', 'tenant_id', 'lead_source_id', 'display_name', 'display_order',
            'is_active', 'reporting_group', 'project_id', 'manager_id', 'visibility',
        )}


class BusinessRuleConfiguration(db.Model):
    __tablename__ = 'business_rule_configurations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    rule_key = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(160), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    definition = db.Column(db.JSON, nullable=False, default=dict)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    effective_from = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    effective_to = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'rule_key', 'version', name='uq_business_rule_version'),
        db.Index('ix_business_rules_tenant_key_active', 'tenant_id', 'rule_key', 'is_active'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'tenant_id': self.tenant_id, 'rule_key': self.rule_key,
            'display_name': self.display_name, 'version': self.version,
            'definition': self.definition or {}, 'is_active': self.is_active,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
        }
