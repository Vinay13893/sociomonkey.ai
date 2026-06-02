from datetime import datetime

from .base import db


PHONE_TYPES = ('primary', 'alternate')


class WhatsAppActivity(db.Model):
    __tablename__ = 'whatsapp_activities'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey('whatsapp_templates.id'), nullable=True)
    template_name = db.Column(db.String(200), nullable=True)
    phone_used = db.Column(db.String(50), nullable=True)
    phone_type = db.Column(db.String(20), nullable=True)  # 'primary' | 'alternate'
    documents_shared = db.Column(db.JSON, nullable=True, default=list)  # list of asset ids
    message_preview = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'lead_id': self.lead_id,
            'user_id': self.user_id,
            'template_id': self.template_id,
            'template_name': self.template_name,
            'phone_used': self.phone_used,
            'phone_type': self.phone_type,
            'documents_shared': self.documents_shared or [],
            'message_preview': self.message_preview,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
