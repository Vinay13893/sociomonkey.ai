"""Unified physical-interaction records and tenant visit configuration."""

from datetime import datetime

from .base import db
from app.utils.time_utils import to_ist_str


class VisitTypeConfiguration(db.Model):
    __tablename__ = 'visit_type_configurations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    internal_key = db.Column(db.String(80), nullable=False)
    display_name = db.Column(db.String(160), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    colour = db.Column(db.String(20), nullable=False, default='#64748b')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    visibility = db.Column(db.String(20), nullable=False, default='VISIBLE')
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'internal_key', name='uq_visit_type_tenant_key'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'internal_key': self.internal_key,
            'display_name': self.display_name, 'display_order': self.display_order,
            'colour': self.colour, 'is_active': self.is_active,
            'visibility': self.visibility,
        }


class VisitStatusConfiguration(db.Model):
    __tablename__ = 'visit_status_configurations'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    internal_key = db.Column(db.String(80), nullable=False)
    display_name = db.Column(db.String(160), nullable=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    colour = db.Column(db.String(20), nullable=False, default='#64748b')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_terminal = db.Column(db.Boolean, nullable=False, default=False)
    visibility = db.Column(db.String(20), nullable=False, default='VISIBLE')
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'internal_key', name='uq_visit_status_tenant_key'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'internal_key': self.internal_key,
            'display_name': self.display_name, 'display_order': self.display_order,
            'colour': self.colour, 'is_active': self.is_active,
            'is_terminal': self.is_terminal, 'visibility': self.visibility,
        }


class Visit(db.Model):
    __tablename__ = 'visits'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    visit_type_key = db.Column(db.String(80), nullable=False, index=True)
    status_key = db.Column(db.String(80), nullable=False, default='SCHEDULED', index=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=False, index=True)
    meeting_room_id = db.Column(db.Integer, db.ForeignKey('meeting_rooms.id'), index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), index=True)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    purpose = db.Column(db.String(250))
    notes = db.Column(db.Text)
    expected_arrival = db.Column(db.DateTime, index=True)
    actual_check_in = db.Column(db.DateTime)
    actual_check_out = db.Column(db.DateTime)
    visitor_count = db.Column(db.Integer, nullable=False, default=1)
    source = db.Column(db.String(120))
    priority = db.Column(db.String(30), nullable=False, default='NORMAL')
    operational_metadata = db.Column(db.JSON, nullable=False, default=dict)
    reception_assigned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    escort_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    token_code = db.Column(db.String(80))
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    archived_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    location = db.relationship('Location')
    meeting_room = db.relationship('MeetingRoom')
    project = db.relationship('Project')
    lead = db.relationship('Lead')
    assigned_user = db.relationship('User', foreign_keys=[assigned_user_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    updater = db.relationship('User', foreign_keys=[updated_by])

    __table_args__ = (
        db.CheckConstraint('visitor_count > 0', name='ck_visit_visitor_count_positive'),
        db.Index('ix_visits_tenant_status_arrival', 'tenant_id', 'status_key', 'expected_arrival'),
        db.Index('ix_visits_tenant_location_active', 'tenant_id', 'location_id', 'is_active'),
    )

    @property
    def duration_minutes(self):
        if not self.actual_check_in or not self.actual_check_out:
            return None
        return max(0, int((self.actual_check_out - self.actual_check_in).total_seconds() // 60))

    @staticmethod
    def _iso(value):
        return to_ist_str(value)

    def to_dict(self, include_details=True):
        data = {
            'id': self.id, 'tenant_id': self.tenant_id,
            'visit_type_key': self.visit_type_key, 'status_key': self.status_key,
            'location_id': self.location_id,
            'location_name': self.location.name if self.location else None,
            'meeting_room_id': self.meeting_room_id,
            'meeting_room_name': self.meeting_room.name if self.meeting_room else None,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'lead_id': self.lead_id,
            'lead_name': self.lead.name if self.lead else None,
            'assigned_user_id': self.assigned_user_id,
            'assigned_user_name': self.assigned_user.name if self.assigned_user else None,
            'purpose': self.purpose, 'expected_arrival': self._iso(self.expected_arrival),
            'actual_check_in': self._iso(self.actual_check_in),
            'actual_check_out': self._iso(self.actual_check_out),
            'duration_minutes': self.duration_minutes, 'visitor_count': self.visitor_count,
            'source': self.source, 'priority': self.priority, 'is_active': self.is_active,
            'archived_at': self._iso(self.archived_at), 'created_at': self._iso(self.created_at),
            'updated_at': self._iso(self.updated_at),
        }
        if include_details:
            data.update({
                'notes': self.notes, 'operational_metadata': self.operational_metadata or {},
                'participants': [row.to_dict() for row in self.participants],
                'tags': [row.tag for row in self.tags],
                'attachments': [row.to_dict() for row in self.attachments],
            })
        return data


class VisitParticipant(db.Model):
    __tablename__ = 'visit_participants'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=False, index=True)
    participant_type = db.Column(db.String(40), nullable=False)
    reference_id = db.Column(db.Integer)
    display_name = db.Column(db.String(200))
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    participant_metadata = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_visit_participants_tenant_type_ref',
                 'tenant_id', 'participant_type', 'reference_id'),
    )

    def to_dict(self):
        return {
            'id': self.id, 'participant_type': self.participant_type,
            'reference_id': self.reference_id, 'display_name': self.display_name,
            'is_primary': self.is_primary,
            'participant_metadata': self.participant_metadata or {},
        }


class VisitTag(db.Model):
    __tablename__ = 'visit_tags'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=False, index=True)
    tag = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('visit_id', 'tag', name='uq_visit_tag'),
    )


class VisitAttachment(db.Model):
    __tablename__ = 'visit_attachments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=False, index=True)
    file_name = db.Column(db.String(250), nullable=False)
    mime_type = db.Column(db.String(120))
    storage_reference = db.Column(db.String(500), nullable=False)
    attachment_metadata = db.Column(db.JSON, nullable=False, default=dict)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'file_name': self.file_name, 'mime_type': self.mime_type,
            'storage_reference': self.storage_reference,
            'attachment_metadata': self.attachment_metadata or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


Visit.participants = db.relationship(
    'VisitParticipant', cascade='all, delete-orphan', lazy='select',
    order_by='VisitParticipant.id',
)
Visit.tags = db.relationship(
    'VisitTag', cascade='all, delete-orphan', lazy='select',
    order_by='VisitTag.id',
)
Visit.attachments = db.relationship(
    'VisitAttachment', cascade='all, delete-orphan', lazy='select',
    order_by='VisitAttachment.id',
)
