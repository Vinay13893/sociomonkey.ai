from datetime import datetime
from .base import db


class Tenant(db.Model):
    __tablename__ = 'tenants'

    id             = db.Column(db.Integer, primary_key=True)
    name           = db.Column(db.String(200), nullable=False)
    slug           = db.Column(db.String(100), unique=True, nullable=False)  # subdomain
    logo_url       = db.Column(db.String(500))
    favicon_url    = db.Column(db.String(500))
    brand_name     = db.Column(db.String(200))           # display name (falls back to name)
    primary_color  = db.Column(db.String(20), default='#1e3a5f')
    secondary_color= db.Column(db.String(20), default='#3b82f6')
    accent_color   = db.Column(db.String(20), default='#10b981')
    sidebar_bg_color = db.Column(db.String(20), default='#1e293b')
    login_bg_color = db.Column(db.String(20), default='#f1f5f9')
    custom_domain  = db.Column(db.String(200))
    plan           = db.Column(db.String(50), default='starter')   # starter / professional / enterprise
    status         = db.Column(db.String(20), default='active')    # active / inactive / suspended / trial / expired / archived
    industry       = db.Column(db.String(100))                     # Real Estate, Tech, etc.
    notes          = db.Column(db.Text)                            # Platform admin notes
    trial_ends_at  = db.Column(db.DateTime)                        # NULL = not on trial
    max_users      = db.Column(db.Integer, default=20)
    admin_email    = db.Column(db.String(200))
    admin_name     = db.Column(db.String(200))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_stats=False):
        d = {
            'id':              self.id,
            'name':            self.name,
            'brand_name':      self.brand_name or self.name,
            'slug':            self.slug,
            'logo_url':        self.logo_url,
            'favicon_url':     self.favicon_url,
            'primary_color':   self.primary_color,
            'secondary_color': self.secondary_color,
            'accent_color':    self.accent_color,
            'sidebar_bg_color': self.sidebar_bg_color or '#1e293b',
            'login_bg_color':  self.login_bg_color or '#f1f5f9',
            'custom_domain':   self.custom_domain,
            'plan':            self.plan,
            'status':          self.status,
            'industry':        self.industry,
            'notes':           self.notes,
            'trial_ends_at':   self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'max_users':       self.max_users,
            'admin_email':     self.admin_email,
            'admin_name':      self.admin_name,
            'created_at':      self.created_at.isoformat(),
            'updated_at':      self.updated_at.isoformat(),
        }
        if include_stats:
            from app.models.user import User
            from app.models.lead import Lead
            d['user_count'] = User.query.filter_by(tenant_id=self.id, is_active=True).count()
            d['lead_count'] = Lead.query.filter_by(tenant_id=self.id, is_active=True).count()
        return d
