from app import db
from datetime import datetime
from sqlalchemy import func

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    permissions = db.Column(db.JSON, default={})
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'permissions': self.permissions
        }

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='team_member')
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    manager = db.relationship('User', remote_side=[id], foreign_keys=[manager_id], backref='team_members')
    assigned_manager = db.relationship('User', remote_side=[id], foreign_keys=[assigned_manager_id])

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'manager_id': self.manager_id,
            'manager_name': self.manager.name if self.manager else None,
            'assigned_manager_id': self.assigned_manager_id,
            'assigned_manager_name': self.assigned_manager.name if self.assigned_manager else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    developer = db.Column(db.String(200))
    project_type = db.Column(db.String(80))
    budget_min = db.Column(db.Float, nullable=True)
    budget_max = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'location': self.location,
            'developer': self.developer,
            'project_type': self.project_type,
            'budget_min': self.budget_min,
            'budget_max': self.budget_max,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    alternate_phone = db.Column(db.String(50))
    email = db.Column(db.String(200))
    source = db.Column(db.String(100))
    budget_min = db.Column(db.Float)
    budget_max = db.Column(db.Float)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    status = db.Column(db.String(80), default='new')
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = db.relationship('Project', backref='leads', lazy='joined')
    assigned_user = db.relationship('User', foreign_keys=[assigned_to], lazy='joined')
    assigned_by_user = db.relationship('User', foreign_keys=[assigned_by])
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'alternate_phone': self.alternate_phone,
            'email': self.email,
            'source': self.source,
            'budget_min': self.budget_min,
            'budget_max': self.budget_max,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'status': self.status,
            'assigned_to': self.assigned_to,
            'assigned_to_name': self.assigned_user.name if self.assigned_user else None,
            'assigned_by': self.assigned_by,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
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
            'changed_by_name': self.changed_by_user.name if self.changed_by_user else None,
            'changed_at': self.changed_at.isoformat()
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
            'created_at': self.created_at.isoformat()
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
            'assigned_from_name': self.assigned_from_user.name if self.assigned_from_user else 'Unassigned',
            'assigned_to': self.assigned_to,
            'assigned_to_name': self.assigned_to_user.name if self.assigned_to_user else 'Unassigned',
            'assigned_by': self.assigned_by,
            'assigned_by_name': self.assigned_by_user.name if self.assigned_by_user else None,
            'reason': self.reason,
            'assigned_at': self.assigned_at.isoformat()
        }

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    resource_id = db.Column(db.Integer, nullable=True)
    resource_type = db.Column(db.String(50), nullable=True)
    old_value = db.Column(db.JSON)
    new_value = db.Column(db.JSON)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    device_info = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else None,
            'action': self.action,
            'module': self.module,
            'resource_id': self.resource_id,
            'resource_type': self.resource_type,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'description': self.description,
            'ip_address': self.ip_address,
            'device_info': self.device_info,
            'created_at': self.created_at.isoformat()
        }
