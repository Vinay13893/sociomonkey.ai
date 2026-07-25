from datetime import datetime
from .base import db
from app.utils.time_utils import to_ist_str


class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    alternate_phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    source = db.Column(db.String(100))
    gclid = db.Column(db.String(255), index=True)
    utm_source = db.Column(db.String(255), index=True)
    utm_medium = db.Column(db.String(255), index=True)
    utm_campaign = db.Column(db.String(255), index=True)
    utm_content = db.Column(db.String(255), index=True)
    utm_term = db.Column(db.String(255), index=True)
    landing_page_url = db.Column(db.Text)
    budget_min = db.Column(db.Float)
    budget_max = db.Column(db.Float)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    channel_partner_id = db.Column(
        db.Integer, db.ForeignKey('channel_partners.id'), nullable=True,
        index=True,
    )
    status = db.Column(db.String(80), default='new')
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    sales_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # Pre-sales team co-owners. Concurrent with assigned_to/sales_manager_id
    # (the sales-side slots) by design: when a lead hands off from calling to
    # sales, the Caller/Calling Manager who worked it stays visibly attached
    # rather than being overwritten - see sync_lead_owner_if_unset /
    # assign_lead_slot in app.services.visit_builder for the write side.
    calling_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    caller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    is_test = db.Column(db.Boolean, default=False, nullable=False, server_default='0', index=True)

    project = db.relationship('Project', backref='leads', lazy='joined')
    channel_partner = db.relationship('ChannelPartner')
    assigned_user = db.relationship('User', foreign_keys=[assigned_to], lazy='joined')
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])
    sales_manager = db.relationship('User', foreign_keys=[sales_manager_id], lazy='joined')
    calling_manager = db.relationship('User', foreign_keys=[calling_manager_id], lazy='joined')
    caller = db.relationship('User', foreign_keys=[caller_id], lazy='joined')
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        # Latest note preview (most recent note text, truncated for table display)
        latest_note = None
        if self.notes:
            sorted_notes = sorted(self.notes, key=lambda n: n.created_at, reverse=True)
            latest_note = sorted_notes[0].note[:120] if sorted_notes else None

        # Next pending callback datetime
        next_callback = None
        if self.callbacks:
            pending = [c for c in self.callbacks if c.status == 'pending' and c.callback_datetime > datetime.utcnow()]
            if pending:
                pending.sort(key=lambda c: c.callback_datetime)
                next_callback = to_ist_str(pending[0].callback_datetime)

        now = datetime.utcnow()
        created_age_days = (now - self.created_at).days if self.created_at else None
        untouched_days = (now - self.updated_at).days if self.updated_at else None

        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'alternate_phone': self.alternate_phone,
            'email': self.email,
            'source': self.source,
            'gclid': self.gclid,
            'utm_source': self.utm_source,
            'utm_medium': self.utm_medium,
            'utm_campaign': self.utm_campaign,
            'utm_content': self.utm_content,
            'utm_term': self.utm_term,
            'landing_page_url': self.landing_page_url,
            'budget_min': self.budget_min,
            'budget_max': self.budget_max,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'channel_partner_id': self.channel_partner_id,
            'channel_partner_name': (
                self.channel_partner.name if self.channel_partner else None
            ),
            'status': self.status,
            'assigned_to': self.assigned_to,
            'assigned_to_name': self.assigned_user.name if self.assigned_user else None,
            'sales_manager_id': self.sales_manager_id,
            'sales_manager_name': self.sales_manager.name if self.sales_manager else None,
            'calling_manager_id': self.calling_manager_id,
            'calling_manager_name': self.calling_manager.name if self.calling_manager else None,
            'caller_id': self.caller_id,
            'caller_name': self.caller.name if self.caller else None,
            'manager_name': (
                self.assigned_user.manager.name
                if self.assigned_user and self.assigned_user.manager
                else None
            ),
            'assigned_by': self.assigned_by,
            'created_by': self.created_by,
            'created_at': to_ist_str(self.created_at),
            'updated_at': to_ist_str(self.updated_at),
            'age_days': created_age_days,
            'untouched_days': untouched_days,
            'is_test': self.is_test,
            'latest_note': latest_note,
            'next_callback': next_callback,
        }


class StatusHistory(db.Model):
    __tablename__ = 'status_history'

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    old_status = db.Column(db.String(80))
    new_status = db.Column(db.String(80), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    lead = db.relationship('Lead', backref='status_history')
    changed_by_user = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'old_status': self.old_status,
            'new_status': self.new_status,
            'changed_by': self.changed_by,
            'changed_by_name': (
                self.changed_by_user.name if self.changed_by_user else None
            ),
            'changed_at': self.changed_at.isoformat(),
        }


class LeadNote(db.Model):
    __tablename__ = 'lead_notes'

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    lead = db.relationship('Lead', backref='notes')
    creator = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'note': self.note,
            'created_by': self.created_by,
            'created_by_name': self.creator.name if self.creator else None,
            'created_at': self.created_at.isoformat(),
        }


class LeadAssignmentHistory(db.Model):
    __tablename__ = 'lead_assignment_history'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    assigned_from = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reason = db.Column(db.Text)
    source = db.Column(db.String(80), nullable=False, default='LEADS')
    correlation_id = db.Column(db.String(36), index=True)
    is_manager_override = db.Column(db.Boolean, nullable=False, default=False)
    # Which of the 4 co-owner slots this entry changed - null for history
    # rows written before co-ownership existed (they were all assigned_to).
    role_slot = db.Column(db.String(20), nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    lead = db.relationship('Lead', backref='assignment_history')
    assigned_from_user = db.relationship('User', foreign_keys=[assigned_from])
    assigned_to_user = db.relationship('User', foreign_keys=[assigned_to])
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'lead_id': self.lead_id,
            'assigned_from': self.assigned_from,
            'assigned_from_name': (
                self.assigned_from_user.name
                if self.assigned_from_user
                else 'Unassigned'
            ),
            'assigned_to': self.assigned_to,
            'assigned_to_name': (
                self.assigned_to_user.name if self.assigned_to_user else 'Unassigned'
            ),
            'assigned_by': self.assigned_by,
            'assigned_by_name': (
                self.assigned_by_user.name if self.assigned_by_user else None
            ),
            'reason': self.reason,
            'source': self.source,
            'correlation_id': self.correlation_id,
            'is_manager_override': self.is_manager_override,
            'role_slot': self.role_slot,
            'assigned_at': self.assigned_at.isoformat(),
        }


class CallbackReminder(db.Model):
    """Scheduled callback / reminder for a lead."""
    __tablename__ = 'callback_reminders'

    id                  = db.Column(db.Integer, primary_key=True)
    lead_id             = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    tenant_id           = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    assigned_user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    manager_id          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    callback_datetime   = db.Column(db.DateTime, nullable=False)
    reminder_10_sent    = db.Column(db.Boolean, default=False, nullable=False)
    reminder_due_sent   = db.Column(db.Boolean, default=False, nullable=False)
    # status: pending | completed | missed | cancelled
    status              = db.Column(db.String(30), default='pending', nullable=False)
    notes               = db.Column(db.Text, nullable=True)
    correlation_id      = db.Column(db.String(36), nullable=True, index=True)
    created_by          = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    lead            = db.relationship('Lead', backref='callbacks')
    assigned_user   = db.relationship('User', foreign_keys=[assigned_user_id])
    manager         = db.relationship('User', foreign_keys=[manager_id])
    creator         = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        return {
            'id':                 self.id,
            'lead_id':            self.lead_id,
            'tenant_id':          self.tenant_id,
            'assigned_user_id':   self.assigned_user_id,
            'assigned_user_name': self.assigned_user.name if self.assigned_user else None,
            'manager_id':         self.manager_id,
            'manager_name':       self.manager.name if self.manager else None,
            'callback_datetime':  to_ist_str(self.callback_datetime),
            'reminder_10_sent':   self.reminder_10_sent,
            'reminder_due_sent':  self.reminder_due_sent,
            'status':             self.status,
            'notes':              self.notes,
            'correlation_id':     self.correlation_id,
            'created_by':         self.created_by,
            'created_at':         to_ist_str(self.created_at),
            'updated_at':         to_ist_str(self.updated_at),
        }
