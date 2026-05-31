from datetime import datetime

from .base import db


class ImportJob(db.Model):
    __tablename__ = 'import_jobs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_slug = db.Column(db.String(80), nullable=True, index=True)
    filename = db.Column(db.String(255), nullable=True)
    file_type = db.Column(db.String(20), nullable=True)
    source_data_b64 = db.Column(db.Text, nullable=True)
    source_mime_type = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(30), default='queued', nullable=False, index=True)
    summary = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'product_slug': self.product_slug,
            'filename': self.filename,
            'file_type': self.file_type,
            'source_mime_type': self.source_mime_type,
            'status': self.status,
            'summary': self.summary,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class ImportJobRow(db.Model):
    __tablename__ = 'import_job_rows'

    id = db.Column(db.Integer, primary_key=True)
    import_job_id = db.Column(db.Integer, db.ForeignKey('import_jobs.id'), nullable=False, index=True)
    row_number = db.Column(db.Integer, nullable=False)
    lead_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(30), default='pending', nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=True)
    errors = db.Column(db.JSON, nullable=True)
    warnings = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    job = db.relationship('ImportJob', backref='rows')

    def to_dict(self):
        return {
            'id': self.id,
            'import_job_id': self.import_job_id,
            'row_number': self.row_number,
            'lead_id': self.lead_id,
            'status': self.status,
            'payload': self.payload,
            'errors': self.errors,
            'warnings': self.warnings,
            'created_at': self.created_at.isoformat(),
        }


class ExportJob(db.Model):
    __tablename__ = 'export_jobs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    product_slug = db.Column(db.String(80), nullable=True, index=True)
    export_type = db.Column(db.String(50), nullable=False, default='leads', index=True)
    filters = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(30), default='queued', nullable=False, index=True)
    artifact_url = db.Column(db.Text, nullable=True)
    artifact_data_b64 = db.Column(db.Text, nullable=True)
    artifact_mime_type = db.Column(db.String(120), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'product_slug': self.product_slug,
            'export_type': self.export_type,
            'filters': self.filters,
            'status': self.status,
            'artifact_url': self.artifact_url,
            'artifact_mime_type': self.artifact_mime_type,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class LeadReshuffleJob(db.Model):
    __tablename__ = 'lead_reshuffle_jobs'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    lead_ids = db.Column(db.JSON, nullable=False)
    strategy = db.Column(db.String(30), nullable=False, default='intelligent', index=True)
    reason = db.Column(db.String(255), nullable=True)
    cooldown_days = db.Column(db.Integer, nullable=False, default=7)
    status = db.Column(db.String(30), default='queued', nullable=False, index=True)
    summary = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'lead_ids': self.lead_ids,
            'strategy': self.strategy,
            'reason': self.reason,
            'cooldown_days': self.cooldown_days,
            'status': self.status,
            'summary': self.summary,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }