from datetime import datetime
from .base import db


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    permissions = db.Column(db.JSON, default=dict)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'permissions': self.permissions,
        }


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='team_member')
    # NULL tenant_id = platform_owner (SocioMonkey global admin)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    tenant = db.relationship('Tenant', foreign_keys=[tenant_id])
    manager = db.relationship(
        'User', remote_side=[id], foreign_keys=[manager_id], backref='team_members'
    )
    assigned_manager = db.relationship(
        'User', remote_side=[id], foreign_keys=[assigned_manager_id]
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'tenant_id': self.tenant_id,
            'tenant_name': self.tenant.name if self.tenant else None,
            'tenant_slug': self.tenant.slug if self.tenant else None,
            'manager_id': self.manager_id,
            'manager_name': self.manager.name if self.manager else None,
            'assigned_manager_id': self.assigned_manager_id,
            'assigned_manager_name': (
                self.assigned_manager.name if self.assigned_manager else None
            ),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
