"""Reusable tenant physical locations and lightweight meeting rooms."""

from datetime import datetime

from .base import db


class TenantBrand(db.Model):
    __tablename__ = 'tenant_brands'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    code = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('tenant_id', 'code', name='uq_tenant_brand_code'),)

    def to_dict(self):
        return {'id': self.id, 'tenant_id': self.tenant_id, 'code': self.code,
                'name': self.name, 'is_active': self.is_active}


class Location(db.Model):
    __tablename__ = 'locations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    brand_id = db.Column(db.Integer, db.ForeignKey('tenant_brands.id'), index=True)
    code = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    location_type = db.Column(db.String(40), nullable=False)
    address_line_1 = db.Column(db.String(250))
    address_line_2 = db.Column(db.String(250))
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    country = db.Column(db.String(120), nullable=False, default='India')
    postal_code = db.Column(db.String(24))
    latitude = db.Column(db.Numeric(10, 7))
    longitude = db.Column(db.Numeric(10, 7))
    contact_details = db.Column(db.JSON, nullable=False, default=dict)
    working_hours = db.Column(db.JSON, nullable=False, default=dict)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    archived_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    brand = db.relationship('TenantBrand')
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'code', name='uq_location_tenant_code'),
        db.Index('ix_locations_tenant_type_active', 'tenant_id', 'location_type', 'is_active'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'tenant_id': self.tenant_id, 'brand_id': self.brand_id,
            'brand_name': self.brand.name if self.brand else None, 'code': self.code,
            'name': self.name, 'location_type': self.location_type,
            'address_line_1': self.address_line_1, 'address_line_2': self.address_line_2,
            'city': self.city, 'state': self.state, 'country': self.country,
            'postal_code': self.postal_code,
            'latitude': float(self.latitude) if self.latitude is not None else None,
            'longitude': float(self.longitude) if self.longitude is not None else None,
            'contact_details': self.contact_details or {}, 'working_hours': self.working_hours or {},
            'notes': self.notes, 'is_active': self.is_active,
            'project_ids': [link.project_id for link in getattr(self, 'project_links', [])],
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
        }


class ProjectLocation(db.Model):
    __tablename__ = 'project_locations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False, index=True)
    relationship_type = db.Column(db.String(40), nullable=False, default='SERVES')
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('project_id', 'location_id', 'relationship_type',
                            name='uq_project_location_relationship'),
    )


Location.project_links = db.relationship(
    'ProjectLocation', foreign_keys='ProjectLocation.location_id',
    cascade='all, delete-orphan', lazy='selectin',
)


class MeetingRoom(db.Model):
    __tablename__ = 'meeting_rooms'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    code = db.Column(db.String(80))
    capacity = db.Column(db.Integer, nullable=False, default=1)
    room_type = db.Column(db.String(80), nullable=False, default='MEETING_ROOM')
    status = db.Column(db.String(30), nullable=False, default='AVAILABLE')
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    notes = db.Column(db.Text)
    archived_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    location = db.relationship('Location')
    __table_args__ = (
        db.UniqueConstraint('location_id', 'name', name='uq_meeting_room_location_name'),
        db.CheckConstraint('capacity > 0', name='ck_meeting_room_capacity_positive'),
        db.Index('ix_meeting_rooms_tenant_location_active', 'tenant_id', 'location_id', 'is_active'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'tenant_id': self.tenant_id, 'location_id': self.location_id,
            'location_name': self.location.name if self.location else None,
            'name': self.name, 'code': self.code, 'capacity': self.capacity,
            'room_type': self.room_type, 'status': self.status, 'is_active': self.is_active,
            'notes': self.notes, 'archived_at': self.archived_at.isoformat() if self.archived_at else None,
        }
