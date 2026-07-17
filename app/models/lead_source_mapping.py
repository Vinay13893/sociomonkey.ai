from datetime import datetime

from .base import db


class LeadSourceFormMapping(db.Model):
    """Per-form project mapping for a lead source (required for source governance)."""
    __tablename__ = 'lead_source_form_mappings'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    source_id = db.Column(db.Integer, db.ForeignKey('lead_sources.id'), nullable=False, index=True)
    source_type = db.Column(db.String(50), nullable=False, default='meta')

    page_id = db.Column(db.String(200))
    form_id = db.Column(db.String(200), nullable=False, index=True)
    form_name = db.Column(db.String(500))

    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)

    # Per-form manager pre-assignment rule
    # none | fixed_manager | round_robin_pool
    manager_assign_mode = db.Column(db.String(40), nullable=False, default='none', server_default='none')
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    rr_manager_pool = db.Column(db.JSON, default=list)
    rr_last_index = db.Column(db.Integer, default=0, nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    source = db.relationship('LeadSource', foreign_keys=[source_id])
    project = db.relationship('Project', foreign_keys=[project_id])
    manager = db.relationship('User', foreign_keys=[manager_id])
    creator = db.relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'source_id', 'form_id', name='uq_form_mapping_tenant_source_form'),
        db.Index('ix_form_mapping_tenant_source_active', 'tenant_id', 'source_id', 'is_active'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'source_id': self.source_id,
            'source_type': self.source_type,
            'page_id': self.page_id,
            'form_id': self.form_id,
            'form_name': self.form_name,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'manager_assign_mode': self.manager_assign_mode or 'none',
            'manager_id': self.manager_id,
            'manager_name': self.manager.name if self.manager else None,
            'rr_manager_pool': self.rr_manager_pool or [],
            'rr_last_index': int(self.rr_last_index or 0),
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class MetaCampaignSnapshot(db.Model):
    """Historical campaign/adset/ad snapshot captured at ingestion time."""
    __tablename__ = 'meta_campaign_snapshots'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    source_id = db.Column(db.Integer, db.ForeignKey('lead_sources.id'), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=True, index=True)
    ingested_log_id = db.Column(db.Integer, db.ForeignKey('ingested_lead_logs.id'), nullable=True, index=True)

    page_id = db.Column(db.String(200))
    form_id = db.Column(db.String(200), index=True)
    form_name = db.Column(db.String(500))

    campaign_id = db.Column(db.String(200), index=True)
    campaign_name = db.Column(db.String(500))
    campaign_status = db.Column(db.String(100))
    campaign_objective = db.Column(db.String(200))

    ad_set_id = db.Column(db.String(200), index=True)
    ad_set_name = db.Column(db.String(500))
    ad_set_status = db.Column(db.String(100))
    optimization_goal = db.Column(db.String(200))

    ad_id = db.Column(db.String(200), index=True)
    ad_name = db.Column(db.String(500))
    ad_status = db.Column(db.String(100))
    creative_name = db.Column(db.String(500))
    is_test = db.Column(db.Boolean, default=False, nullable=False, server_default='0', index=True)

    spend = db.Column(db.Float)
    impressions = db.Column(db.Integer)
    reach = db.Column(db.Integer)
    clicks = db.Column(db.Integer)
    ctr = db.Column(db.Float)
    cpc = db.Column(db.Float)
    cpm = db.Column(db.Float)
    frequency = db.Column(db.Float)
    results = db.Column(db.Integer)
    cost_per_result = db.Column(db.Float)

    audience = db.Column(db.String(500))
    placement = db.Column(db.String(500))
    age_range = db.Column(db.String(120))
    gender = db.Column(db.String(120))
    geo = db.Column(db.String(200))

    extra_metrics = db.Column(db.JSON, default=dict)
    snapshot_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    source = db.relationship('LeadSource', foreign_keys=[source_id])
    lead = db.relationship('Lead', foreign_keys=[lead_id])

    __table_args__ = (
        db.Index('ix_meta_snapshot_tenant_snapshot_at', 'tenant_id', 'snapshot_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'source_id': self.source_id,
            'lead_id': self.lead_id,
            'ingested_log_id': self.ingested_log_id,
            'page_id': self.page_id,
            'form_id': self.form_id,
            'form_name': self.form_name,
            'campaign_id': self.campaign_id,
            'campaign_name': self.campaign_name,
            'campaign_status': self.campaign_status,
            'campaign_objective': self.campaign_objective,
            'ad_set_id': self.ad_set_id,
            'ad_set_name': self.ad_set_name,
            'ad_set_status': self.ad_set_status,
            'optimization_goal': self.optimization_goal,
            'ad_id': self.ad_id,
            'ad_name': self.ad_name,
            'ad_status': self.ad_status,
            'creative_name': self.creative_name,
            'is_test': self.is_test,
            'spend': self.spend,
            'impressions': self.impressions,
            'reach': self.reach,
            'clicks': self.clicks,
            'ctr': self.ctr,
            'cpc': self.cpc,
            'cpm': self.cpm,
            'frequency': self.frequency,
            'results': self.results,
            'cost_per_result': self.cost_per_result,
            'audience': self.audience,
            'placement': self.placement,
            'age_range': self.age_range,
            'gender': self.gender,
            'geo': self.geo,
            'extra_metrics': self.extra_metrics or {},
            'snapshot_at': self.snapshot_at.isoformat() if self.snapshot_at else None,
        }
