from datetime import datetime
from .base import db


class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    source = db.Column(db.String(100))
    budget_min = db.Column(db.Float)
    budget_max = db.Column(db.Float)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    status = db.Column(db.String(80), default='new')
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    sales_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default='1')

    project = db.relationship('Project', backref='leads', lazy='joined')
    assigned_user = db.relationship('User', foreign_keys=[assigned_to], lazy='joined')
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])
    sales_manager = db.relationship('User', foreign_keys=[sales_manager_id], lazy='joined')
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'source': self.source,
            'budget_min': self.budget_min,
            'budget_max': self.budget_max,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'status': self.status,
            'assigned_to': self.assigned_to,
            'assigned_to_name': self.assigned_user.name if self.assigned_user else None,
            'sales_manager_id': self.sales_manager_id,
            'sales_manager_name': self.sales_manager.name if self.sales_manager else None,
            'manager_name': (
                self.assigned_user.manager.name
                if self.assigned_user and self.assigned_user.manager
                else None
            ),
            'assigned_by': self.assigned_by,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
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
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    assigned_from = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reason = db.Column(db.Text)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    lead = db.relationship('Lead', backref='assignment_history')
    assigned_from_user = db.relationship('User', foreign_keys=[assigned_from])
    assigned_to_user = db.relationship('User', foreign_keys=[assigned_to])
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])

    def to_dict(self):
        return {
            'id': self.id,
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
            'assigned_at': self.assigned_at.isoformat(),
        }
