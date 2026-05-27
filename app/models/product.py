"""
Product, TenantProduct, FeatureFlag, UsageLog models.

These form the core of the SocioMonkey multi-product SaaS platform layer.

    Product         — a SaaS module (CRM, WMS, Procurement, HRMS, …)
    TenantProduct   — which products a tenant has subscribed to
    FeatureFlag     — per-product or per-tenant feature toggles
    UsageLog        — lightweight audit trail of product usage events
"""
from datetime import datetime
import json

from .base import db


class Product(db.Model):
    __tablename__ = 'products'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(200), nullable=False)
    slug            = db.Column(db.String(100), unique=True, nullable=False)   # e.g. "crm", "wms"
    description     = db.Column(db.Text)
    icon            = db.Column(db.String(10), default='📦')                   # emoji icon
    color           = db.Column(db.String(20), default='#3b82f6')
    category        = db.Column(db.String(100), default='General')             # e.g. Sales, Operations
    version         = db.Column(db.String(20), default='1.0.0')
    is_active       = db.Column(db.Boolean, default=True)
    is_public       = db.Column(db.Boolean, default=True)                      # show in product catalog
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant_products = db.relationship('TenantProduct', backref='product', lazy='dynamic',
                                      cascade='all, delete-orphan')
    feature_flags   = db.relationship('FeatureFlag', backref='product', lazy='dynamic',
                                      foreign_keys='FeatureFlag.product_id')

    def to_dict(self, include_stats=False):
        d = {
            'id':          self.id,
            'name':        self.name,
            'slug':        self.slug,
            'description': self.description,
            'icon':        self.icon,
            'color':       self.color,
            'category':    self.category,
            'version':     self.version,
            'is_active':   self.is_active,
            'is_public':   self.is_public,
            'created_at':  self.created_at.isoformat(),
        }
        if include_stats:
            d['tenant_count'] = self.tenant_products.filter_by(status='active').count()
        return d


class TenantProduct(db.Model):
    """Subscription / enablement record linking a Tenant to a Product."""
    __tablename__ = 'tenant_products'
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'product_id', name='uq_tenant_product'),
    )

    id          = db.Column(db.Integer, primary_key=True)
    tenant_id   = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    status      = db.Column(db.String(20), default='active')   # active / suspended / trial / expired
    settings    = db.Column(db.Text)                           # JSON blob for per-product tenant settings
    enabled_at  = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at  = db.Column(db.DateTime)                       # NULL = no expiry

    def get_settings(self):
        try:
            return json.loads(self.settings) if self.settings else {}
        except Exception:
            return {}

    def to_dict(self):
        return {
            'id':         self.id,
            'tenant_id':  self.tenant_id,
            'product_id': self.product_id,
            'product':    self.product.to_dict() if self.product else None,
            'status':     self.status,
            'settings':   self.get_settings(),
            'enabled_at': self.enabled_at.isoformat() if self.enabled_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }


class FeatureFlag(db.Model):
    """
    Feature toggles — can be global, product-scoped, or tenant-scoped.
    Precedence (most specific wins): tenant > product > global.
    """
    __tablename__ = 'feature_flags'

    id          = db.Column(db.Integer, primary_key=True)
    flag_key    = db.Column(db.String(200), nullable=False)       # e.g. "bulk_import", "ai_suggestions"
    flag_value  = db.Column(db.Text)                              # JSON-encoded value
    is_enabled  = db.Column(db.Boolean, default=True)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    tenant_id   = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    description = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':          self.id,
            'flag_key':    self.flag_key,
            'flag_value':  self.flag_value,
            'is_enabled':  self.is_enabled,
            'product_id':  self.product_id,
            'tenant_id':   self.tenant_id,
            'description': self.description,
        }


class UsageLog(db.Model):
    """Lightweight event log for tracking product usage per tenant."""
    __tablename__ = 'usage_logs'

    id          = db.Column(db.Integer, primary_key=True)
    tenant_id   = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    product_id  = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action      = db.Column(db.String(100), nullable=False)   # e.g. "page_view", "api_call"
    resource    = db.Column(db.String(200))                   # e.g. "leads", "pipeline"
    log_data    = db.Column(db.Text)                          # JSON (renamed from metadata)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id':         self.id,
            'tenant_id':  self.tenant_id,
            'product_id': self.product_id,
            'user_id':    self.user_id,
            'action':     self.action,
            'resource':   self.resource,
            'created_at': self.created_at.isoformat(),
        }
