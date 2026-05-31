from io import BytesIO

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from app.middleware import require_auth, require_role
from app.models.base import db
from app.models.project import Project
from app.models.project_asset import ProjectAsset
from app.utils.activity import log_activity

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')

ALLOWED_ASSET_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.xlsx', '.xls', '.doc', '.docx', '.zip'}
ALLOWED_ASSET_MIMES = {
    'application/pdf',
    'image/png', 'image/jpeg', 'image/gif', 'image/webp',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/zip',
    'application/x-zip-compressed',
}


def _can_access_project(project, tenant_id):
    return project and project.tenant_id == tenant_id and project.is_active


def _asset_ext(name):
    lower = (name or '').lower()
    dot = lower.rfind('.')
    return lower[dot:] if dot >= 0 else ''


@projects_bp.route('', methods=['GET'])
@require_auth
def get_projects():
    tid = request.current_tenant_id
    projects = Project.query.filter_by(is_active=True, tenant_id=tid).all()
    return jsonify({'projects': [p.to_dict() for p in projects]}), 200


@projects_bp.route('', methods=['POST'])
@require_role('superadmin')
def create_project():
    user = request.current_user
    data = request.get_json() or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Project name is required'}), 400
    tid = user.tenant_id
    if Project.query.filter_by(name=name, tenant_id=tid).first():
        return jsonify({'error': 'Project already exists'}), 400

    project = Project(
        name=name,
        description=data.get('description'),
        location=data.get('location'),
        developer=data.get('developer'),
        project_type=data.get('project_type'),
        budget_min=data.get('budget_min'),
        budget_max=data.get('budget_max'),
        tenant_id=tid,
        created_by=user.id,
    )
    db.session.add(project)
    db.session.commit()

    log_activity(
        user.id, 'create_project', 'projects', project.id, 'Project',
        description=f'Created project {project.name}',
    )
    return jsonify({'project': project.to_dict()}), 201


@projects_bp.route('/<int:project_id>', methods=['GET'])
@require_auth
def get_project(project_id):
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    return jsonify({'project': project.to_dict()}), 200


@projects_bp.route('/<int:project_id>', methods=['PUT'])
@require_role('superadmin')
def update_project(project_id):
    user = request.current_user
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data = request.get_json() or {}
    old_data = project.to_dict()

    project.name = data.get('name', project.name)
    project.description = data.get('description', project.description)
    project.location = data.get('location', project.location)
    project.developer = data.get('developer', project.developer)
    project.project_type = data.get('project_type', project.project_type)
    project.budget_min = data.get('budget_min', project.budget_min)
    project.budget_max = data.get('budget_max', project.budget_max)

    db.session.commit()

    log_activity(
        user.id, 'update_project', 'projects', project_id, 'Project',
        old_value=old_data, new_value=project.to_dict(),
        description=f'Updated project {project.name}',
    )
    return jsonify({'project': project.to_dict()}), 200


@projects_bp.route('/<int:project_id>', methods=['DELETE'])
@require_role('superadmin')
def delete_project(project_id):
    user = request.current_user
    project = Project.query.get(project_id)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    project.is_active = False
    db.session.commit()

    log_activity(
        user.id, 'delete_project', 'projects', project_id, 'Project',
        description=f'Deleted project {project.name}',
    )
    return jsonify({'message': 'Project deleted'}), 200


@projects_bp.route('/<int:project_id>/assets', methods=['GET'])
@require_auth
def list_project_assets(project_id):
    tid = request.current_tenant_id
    project = Project.query.get(project_id)
    if not _can_access_project(project, tid):
        return jsonify({'error': 'Project not found'}), 404

    assets = (
        ProjectAsset.query
        .filter_by(project_id=project_id, tenant_id=tid)
        .order_by(ProjectAsset.uploaded_at.desc())
        .all()
    )
    return jsonify({'assets': [a.to_dict() for a in assets]}), 200


@projects_bp.route('/<int:project_id>/assets', methods=['POST'])
@require_auth
def upload_project_asset(project_id):
    user = request.current_user
    tid = request.current_tenant_id
    project = Project.query.get(project_id)
    if not _can_access_project(project, tid):
        return jsonify({'error': 'Project not found'}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'file is required'}), 400
    file = request.files['file']
    if not file or not file.filename:
        return jsonify({'error': 'file is required'}), 400

    safe_name = secure_filename(file.filename)
    ext = _asset_ext(safe_name)
    mime_type = (file.mimetype or '').lower()
    if ext not in ALLOWED_ASSET_EXTENSIONS:
        return jsonify({'error': 'Unsupported file type'}), 400
    if mime_type and mime_type not in ALLOWED_ASSET_MIMES:
        return jsonify({'error': 'Unsupported file type'}), 400

    payload = file.read()
    if not payload:
        return jsonify({'error': 'Empty file'}), 400

    asset = ProjectAsset(
        tenant_id=tid,
        project_id=project_id,
        file_name=safe_name,
        mime_type=mime_type or 'application/octet-stream',
        file_size=len(payload),
        file_data=payload,
        uploaded_by=user.id,
    )
    db.session.add(asset)
    db.session.commit()

    log_activity(
        user.id, 'upload_project_asset', 'projects', project_id, 'ProjectAsset',
        description=f'Uploaded asset {safe_name} for project {project.name}',
    )
    return jsonify({'asset': asset.to_dict()}), 201


@projects_bp.route('/<int:project_id>/assets/<int:asset_id>/download', methods=['GET'])
@require_auth
def download_project_asset(project_id, asset_id):
    tid = request.current_tenant_id
    project = Project.query.get(project_id)
    if not _can_access_project(project, tid):
        return jsonify({'error': 'Project not found'}), 404

    asset = ProjectAsset.query.filter_by(id=asset_id, project_id=project_id, tenant_id=tid).first()
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    return send_file(
        BytesIO(asset.file_data),
        mimetype=asset.mime_type or 'application/octet-stream',
        as_attachment=True,
        download_name=asset.file_name,
    )


@projects_bp.route('/<int:project_id>/assets/<int:asset_id>/view', methods=['GET'])
@require_auth
def view_project_asset(project_id, asset_id):
    tid = request.current_tenant_id
    project = Project.query.get(project_id)
    if not _can_access_project(project, tid):
        return jsonify({'error': 'Project not found'}), 404

    asset = ProjectAsset.query.filter_by(id=asset_id, project_id=project_id, tenant_id=tid).first()
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    return send_file(
        BytesIO(asset.file_data),
        mimetype=asset.mime_type or 'application/octet-stream',
        as_attachment=False,
        download_name=asset.file_name,
    )
