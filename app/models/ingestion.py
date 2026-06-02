"""
Lead Ingestion Engine – Database Models
========================================
LeadSource      — per-tenant source configuration (Meta, Google, Webhook, …)
IngestedLeadLog — raw-payload audit trail for every inbound event
"""

import secrets
from datetime import datetime
from .base import db


# ── Source type registry ───────────────────────────────────────────────────────
# Add new source types here ONLY – no other code changes needed for new channels
SOURCE_TYPES = (
    'meta',         # Facebook + Instagram Lead Ads
    'google',       # Google Lead Form / Google Ads Lead Form
    'webhook',      # Generic custom webhook (website forms, portals, etc.)
    'housing',      # Housing.com (future)
    'magicbricks',  # MagicBricks (future)
    'ninetynineacres',  # 99acres (future)
    'indiamart',    # IndiaMART (future)
    'whatsapp_form', # WhatsApp Lead Forms (future)
)

# ── Duplicate handling modes ───────────────────────────────────────────────────
DUP_MODES = ('skip', 'update', 'create_duplicate', 'flag')

# ── Assignment strategy types ──────────────────────────────────────────────────
ASSIGN_STRATEGIES = ('none', 'round_robin', 'fixed_user', 'project_based', 'manager_based')


def _generate_webhook_secret():
    return secrets.token_hex(32)


class LeadSource(db.Model):
    """
    One row per lead-capture channel per tenant.
    Stores credentials, field mapping, duplicate rules, and assignment config.
    """
    __tablename__ = 'lead_sources'

    id              = db.Column(db.Integer, primary_key=True)
    tenant_id       = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)

    # ── Identity ──────────────────────────────────────────────────────────────
    name            = db.Column(db.String(200), nullable=False)   # human label, e.g. "Ganga FB Ads"
    source_type     = db.Column(db.String(50),  nullable=False)   # see SOURCE_TYPES
    is_active       = db.Column(db.Boolean, default=True, nullable=False)
    webhook_secret  = db.Column(db.String(80),  nullable=False, default=_generate_webhook_secret)
    # Unique inbound URL token: /api/ingestion/<source_type>/<webhook_token>
    webhook_token   = db.Column(db.String(80),  nullable=False, unique=True,
                                default=lambda: secrets.token_urlsafe(24))

    # ── OAuth / Platform credentials (stored as JSON blob) ────────────────────
    # Meta:   {access_token, page_id, form_id, app_id, app_secret}
    # Google: {client_id, client_secret, refresh_token, customer_id, form_id}
    # Webhook: {} (uses HMAC via webhook_secret)
    credentials     = db.Column(db.JSON, default=dict)

    # ── Connection metadata (populated after successful test/auth) ─────────────
    connected_account   = db.Column(db.String(500))   # e.g. "Ganga Realty Page"
    permission_status   = db.Column(db.String(50))    # 'ok' | 'partial' | 'missing' | 'error'
    permission_details  = db.Column(db.JSON, default=dict)   # {missing: [...], granted: [...]}
    available_forms     = db.Column(db.JSON, default=list)   # [{id, name, ...}]
    available_campaigns = db.Column(db.JSON, default=list)   # [{id, name, ...}]
    last_tested_at      = db.Column(db.DateTime)
    last_test_result    = db.Column(db.String(50))    # 'pass' | 'fail'
    last_test_message   = db.Column(db.Text)

    # ── Field mapping (JSON dict) ──────────────────────────────────────────────
    # Maps source field names → LMS field names
    # e.g. {"full_name": "name", "mobile": "phone", "city": "source"}
    field_mapping       = db.Column(db.JSON, default=dict)

    # ── Default values applied to every ingested lead ─────────────────────────
    # e.g. {"project_id": 5, "source": "Facebook", "status": "new"}
    default_values      = db.Column(db.JSON, default=dict)

    # ── Duplicate detection ────────────────────────────────────────────────────
    dup_check_phone     = db.Column(db.Boolean, default=True,  nullable=False)
    dup_check_email     = db.Column(db.Boolean, default=True,  nullable=False)
    dup_mode            = db.Column(db.String(30), default='skip')  # see DUP_MODES

    # ── Assignment engine ──────────────────────────────────────────────────────
    assign_strategy     = db.Column(db.String(30), default='none')   # see ASSIGN_STRATEGIES
    assign_fixed_user_id= db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assign_manager_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # Round-robin state: index of the last assigned user
    rr_last_index       = db.Column(db.Integer, default=0)
    # JSON list of user IDs for round-robin pool
    rr_user_pool        = db.Column(db.JSON, default=list)

    # ── Stats ──────────────────────────────────────────────────────────────────
    total_leads_ingested= db.Column(db.Integer, default=0, nullable=False)
    total_errors        = db.Column(db.Integer, default=0, nullable=False)
    last_lead_at        = db.Column(db.DateTime)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at          = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow,
                                    onupdate=datetime.utcnow, nullable=False)
    created_by          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    tenant          = db.relationship('Tenant', foreign_keys=[tenant_id])
    fixed_user      = db.relationship('User', foreign_keys=[assign_fixed_user_id])
    assign_manager  = db.relationship('User', foreign_keys=[assign_manager_id])
    creator         = db.relationship('User', foreign_keys=[created_by])

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        db.Index('ix_lead_sources_tenant_active', 'tenant_id', 'is_active'),
        db.Index('ix_lead_sources_webhook_token', 'webhook_token'),
    )

    def to_dict(self, safe=True):
        creds = dict(self.credentials or {})
        if safe:
            # Never expose secrets/tokens in API responses
            for k in ('access_token', 'app_secret', 'client_secret', 'refresh_token'):
                if k in creds:
                    creds[k] = '••••••••'
        return {
            'id':                   self.id,
            'tenant_id':            self.tenant_id,
            'name':                 self.name,
            'source_type':          self.source_type,
            'is_active':            self.is_active,
            'webhook_token':        self.webhook_token,
            'webhook_url':          f'/api/ingestion/{self.source_type}/{self.webhook_token}',
            'credentials':          creds,
            'connected_account':    self.connected_account,
            'permission_status':    self.permission_status,
            'permission_details':   self.permission_details or {},
            'available_forms':      self.available_forms or [],
            'available_campaigns':  self.available_campaigns or [],
            'last_tested_at':       self.last_tested_at.isoformat() if self.last_tested_at else None,
            'last_test_result':     self.last_test_result,
            'last_test_message':    self.last_test_message,
            'field_mapping':        self.field_mapping or {},
            'default_values':       self.default_values or {},
            'dup_check_phone':      self.dup_check_phone,
            'dup_check_email':      self.dup_check_email,
            'dup_mode':             self.dup_mode,
            'assign_strategy':      self.assign_strategy,
            'assign_fixed_user_id': self.assign_fixed_user_id,
            'assign_manager_id':    self.assign_manager_id,
            'rr_user_pool':         self.rr_user_pool or [],
            'total_leads_ingested': self.total_leads_ingested,
            'total_errors':         self.total_errors,
            'last_lead_at':         self.last_lead_at.isoformat() if self.last_lead_at else None,
            'created_at':           self.created_at.isoformat(),
            'updated_at':           self.updated_at.isoformat(),
        }


class IngestedLeadLog(db.Model):
    """
    Audit trail of every inbound event.
    Kept regardless of success / failure so nothing is ever lost.
    """
    __tablename__ = 'ingested_lead_logs'

    id              = db.Column(db.Integer, primary_key=True)
    tenant_id       = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    source_id       = db.Column(db.Integer, db.ForeignKey('lead_sources.id'), nullable=False, index=True)
    source_type     = db.Column(db.String(50), nullable=False)

    # Raw payload exactly as received
    raw_payload     = db.Column(db.JSON)
    # Mapped fields (post field-mapping, pre-lead creation)
    mapped_fields   = db.Column(db.JSON)

    # Platform-specific metadata
    platform_lead_id    = db.Column(db.String(200))   # e.g. Meta lead_id
    campaign_id         = db.Column(db.String(200))
    campaign_name       = db.Column(db.String(500))
    ad_set_id           = db.Column(db.String(200))
    ad_set_name         = db.Column(db.String(500))
    ad_id               = db.Column(db.String(200))
    ad_name             = db.Column(db.String(500))
    form_id             = db.Column(db.String(200))
    form_name           = db.Column(db.String(500))
    page_id             = db.Column(db.String(200))

    # Processing outcome
    # status: queued | processed | duplicate | error
    status          = db.Column(db.String(30), default='queued', nullable=False, index=True)
    error_message   = db.Column(db.Text)
    # ID of the LMS lead created (or existing lead updated)
    lead_id         = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=True)
    dup_of_lead_id  = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=True)

    received_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    processed_at    = db.Column(db.DateTime)

    source          = db.relationship('LeadSource', foreign_keys=[source_id])
    lead            = db.relationship('Lead', foreign_keys=[lead_id])
    dup_lead        = db.relationship('Lead', foreign_keys=[dup_of_lead_id])

    __table_args__ = (
        db.Index('ix_ingested_log_source_status', 'source_id', 'status'),
        db.Index('ix_ingested_log_tenant_received', 'tenant_id', 'received_at'),
    )

    def to_dict(self):
        return {
            'id':               self.id,
            'tenant_id':        self.tenant_id,
            'source_id':        self.source_id,
            'source_type':      self.source_type,
            'platform_lead_id': self.platform_lead_id,
            'campaign_name':    self.campaign_name,
            'ad_name':          self.ad_name,
            'form_name':        self.form_name,
            'mapped_fields':    self.mapped_fields or {},
            'status':           self.status,
            'error_message':    self.error_message,
            'lead_id':          self.lead_id,
            'dup_of_lead_id':   self.dup_of_lead_id,
            'received_at':      self.received_at.isoformat(),
            'processed_at':     self.processed_at.isoformat() if self.processed_at else None,
        }
