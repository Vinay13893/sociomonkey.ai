from datetime import datetime

from .base import db


class DemoRequest(db.Model):
    __tablename__ = 'demo_requests'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False, index=True)
    phone = db.Column(db.String(50))
    message = db.Column(db.Text)
    product_code = db.Column(db.String(100))
    product_name = db.Column(db.String(200))
    source = db.Column(db.String(100), default='product_hub')
    status = db.Column(db.String(50), default='new')
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'company': self.company,
            'email': self.email,
            'phone': self.phone,
            'message': self.message,
            'product_code': self.product_code,
            'product_name': self.product_name,
            'source': self.source,
            'status': self.status,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }