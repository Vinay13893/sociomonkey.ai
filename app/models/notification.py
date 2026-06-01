from datetime import datetime

from .base import db
from app.utils.time_utils import to_ist_str


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, default='system')
    kind = db.Column(db.String(50), nullable=False, default='info')
    title = db.Column(db.String(200), nullable=True)
    message = db.Column(db.Text, nullable=False)
    payload = db.Column(db.JSON, nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    source = db.Column(db.String(80), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'category': self.category,
            'kind': self.kind,
            'title': self.title,
            'message': self.message,
            'payload': self.payload,
            'is_read': self.is_read,
            'read_at': to_ist_str(self.read_at),
            'source': self.source,
            'expires_at': to_ist_str(self.expires_at),
            'created_at': to_ist_str(self.created_at),
        }