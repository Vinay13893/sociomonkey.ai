from datetime import datetime

from .base import db


class ProjectAsset(db.Model):
    __tablename__ = 'project_assets'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    file_name = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(120), nullable=False)
    file_size = db.Column(db.Integer, nullable=False, default=0)
    file_data = db.Column(db.LargeBinary, nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    project = db.relationship('Project', backref='assets')

    def to_dict(self):
        uploader_name = None
        if self.uploaded_by:
            from app.models.user import User
            uploader = User.query.get(self.uploaded_by)
            uploader_name = uploader.name if uploader else None

        return {
            'id': self.id,
            'project_id': self.project_id,
            'file_name': self.file_name,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'uploaded_by': self.uploaded_by,
            'uploaded_by_name': uploader_name,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
        }
