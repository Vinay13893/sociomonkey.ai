from datetime import datetime

from .base import db


class OAuthSession(db.Model):
    __tablename__ = 'oauth_sessions'

    session_key = db.Column(db.String(128), primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    platform = db.Column(db.String(32), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
