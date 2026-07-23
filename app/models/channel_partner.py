"""Tenant-scoped Channel Partner relationship foundation."""

from datetime import datetime

from .base import db
from app.utils.time_utils import to_ist_str


def _mask_phone(value):
    raw = str(value or '')
    return ('*' * max(0, len(raw) - 4)) + raw[-4:] if raw else raw


def _mask_email(value):
    raw = str(value or '')
    if '@' not in raw:
        return '***' if raw else raw
    local, domain = raw.split('@', 1)
    return f'{local[:1]}***@{domain}'


def _mask_identifier(value):
    raw = str(value or '')
    return f'****{raw[-4:]}' if raw else None


class ChannelPartner(db.Model):
    __tablename__ = 'channel_partners'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    code = db.Column(db.String(80), nullable=False)
    partner_type = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    organisation_name = db.Column(db.String(240))
    gst_number = db.Column(db.String(40))
    pan_number = db.Column(db.String(20))
    rera_number = db.Column(db.String(100))
    address_line_1 = db.Column(db.String(250))
    address_line_2 = db.Column(db.String(250))
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    country = db.Column(db.String(120), nullable=False, default='India')
    postal_code = db.Column(db.String(24))
    tags = db.Column(db.JSON, nullable=False, default=list)
    notes = db.Column(db.Text)
    profile_metadata = db.Column(db.JSON, nullable=False, default=dict)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    archived_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id', 'code', name='uq_channel_partner_tenant_code'
        ),
        db.CheckConstraint(
            "partner_type IN ('INDIVIDUAL','ORGANISATION')",
            name='ck_channel_partner_type',
        ),
        db.Index(
            'ix_channel_partners_tenant_type_active',
            'tenant_id', 'partner_type', 'is_active',
        ),
    )

    def to_dict(self, include_details=False, reveal_sensitive=False):
        primary = next(
            (row for row in self.contacts if row.is_primary and row.is_active),
            next((row for row in self.contacts if row.is_active), None),
        )
        data = {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'code': self.code,
            'partner_type': self.partner_type,
            'name': self.name,
            'organisation_name': self.organisation_name,
            'primary_contact': (
                primary.to_dict(reveal_sensitive=reveal_sensitive)
                if primary else None
            ),
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'tags': self.tags or [],
            'is_active': self.is_active,
            'archived_at': to_ist_str(self.archived_at),
            'created_at': to_ist_str(self.created_at),
            'updated_at': to_ist_str(self.updated_at),
        }
        if include_details:
            data.update({
                'gst_number': (
                    self.gst_number if reveal_sensitive
                    else _mask_identifier(self.gst_number)
                ),
                'pan_number': (
                    self.pan_number if reveal_sensitive
                    else _mask_identifier(self.pan_number)
                ),
                'rera_number': (
                    self.rera_number if reveal_sensitive
                    else _mask_identifier(self.rera_number)
                ),
                'address_line_1': self.address_line_1,
                'address_line_2': self.address_line_2,
                'postal_code': self.postal_code,
                'notes': self.notes,
                'profile_metadata': self.profile_metadata or {},
                'contacts': [
                    row.to_dict(reveal_sensitive=reveal_sensitive)
                    for row in self.contacts
                ],
                'project_associations': [
                    row.to_dict() for row in self.project_associations
                ],
                'assignments': [row.to_dict() for row in self.assignments],
            })
        return data


class ChannelPartnerContact(db.Model):
    __tablename__ = 'channel_partner_contacts'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    channel_partner_id = db.Column(
        db.Integer, db.ForeignKey('channel_partners.id'),
        nullable=False, index=True,
    )
    name = db.Column(db.String(200), nullable=False)
    designation = db.Column(db.String(120))
    mobile_numbers = db.Column(db.JSON, nullable=False, default=list)
    email_addresses = db.Column(db.JSON, nullable=False, default=list)
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    contact_metadata = db.Column(db.JSON, nullable=False, default=dict)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    archived_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.Index(
            'ix_channel_partner_contacts_tenant_partner_active',
            'tenant_id', 'channel_partner_id', 'is_active',
        ),
    )

    def to_dict(self, reveal_sensitive=False):
        mobiles = self.mobile_numbers or []
        emails = self.email_addresses or []
        return {
            'id': self.id,
            'channel_partner_id': self.channel_partner_id,
            'name': self.name,
            'designation': self.designation,
            'mobile_numbers': (
                mobiles if reveal_sensitive else [_mask_phone(value) for value in mobiles]
            ),
            'email_addresses': (
                emails if reveal_sensitive else [_mask_email(value) for value in emails]
            ),
            'is_primary': self.is_primary,
            'contact_metadata': self.contact_metadata or {},
            'is_active': self.is_active,
            'archived_at': to_ist_str(self.archived_at),
            'created_at': to_ist_str(self.created_at),
            'updated_at': to_ist_str(self.updated_at),
        }


class ChannelPartnerProject(db.Model):
    __tablename__ = 'channel_partner_projects'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    channel_partner_id = db.Column(
        db.Integer, db.ForeignKey('channel_partners.id'),
        nullable=False, index=True,
    )
    project_id = db.Column(
        db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True
    )
    relationship_type = db.Column(db.String(30), nullable=False, default='ACTIVE')
    effective_from = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )
    effective_to = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project = db.relationship('Project')

    __table_args__ = (
        db.CheckConstraint(
            "relationship_type IN ('PREFERRED','ACTIVE','HISTORICAL')",
            name='ck_channel_partner_project_type',
        ),
        db.Index(
            'ix_channel_partner_projects_tenant_project_active',
            'tenant_id', 'project_id', 'is_active',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'relationship_type': self.relationship_type,
            'effective_from': to_ist_str(self.effective_from),
            'effective_to': to_ist_str(self.effective_to),
            'is_active': self.is_active,
        }


class ChannelPartnerAssignment(db.Model):
    __tablename__ = 'channel_partner_assignments'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    channel_partner_id = db.Column(
        db.Integer, db.ForeignKey('channel_partners.id'),
        nullable=False, index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )
    assignment_type = db.Column(db.String(40), nullable=False)
    effective_from = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )
    effective_to = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.CheckConstraint(
            "assignment_type IN "
            "('SALES_MANAGER','RELATIONSHIP_MANAGER','SECONDARY_RM')",
            name='ck_channel_partner_assignment_type',
        ),
        db.Index(
            'ix_channel_partner_assignments_tenant_user_active',
            'tenant_id', 'user_id', 'is_active',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else None,
            'assignment_type': self.assignment_type,
            'effective_from': to_ist_str(self.effective_from),
            'effective_to': to_ist_str(self.effective_to),
            'is_active': self.is_active,
        }


class ChannelPartnerNote(db.Model):
    __tablename__ = 'channel_partner_notes'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(
        db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True
    )
    channel_partner_id = db.Column(
        db.Integer, db.ForeignKey('channel_partners.id'),
        nullable=False, index=True,
    )
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    author = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'is_active': self.is_active,
            'created_by': self.created_by,
            'created_by_name': self.author.name if self.author else None,
            'created_at': to_ist_str(self.created_at),
        }


ChannelPartner.contacts = db.relationship(
    'ChannelPartnerContact', cascade='all, delete-orphan', lazy='select',
    order_by='ChannelPartnerContact.is_primary.desc(), ChannelPartnerContact.id',
)
ChannelPartner.project_associations = db.relationship(
    'ChannelPartnerProject', cascade='all, delete-orphan', lazy='select',
    order_by='ChannelPartnerProject.id',
)
ChannelPartner.assignments = db.relationship(
    'ChannelPartnerAssignment', cascade='all, delete-orphan', lazy='select',
    order_by='ChannelPartnerAssignment.id',
)
ChannelPartner.timeline_notes = db.relationship(
    'ChannelPartnerNote', cascade='all, delete-orphan', lazy='select',
    order_by='ChannelPartnerNote.id',
)
