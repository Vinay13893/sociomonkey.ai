from flask import Blueprint, jsonify, request

from app.middleware import require_auth, require_role
from app.models.base import db
from app.models.project import Project
from app.utils.activity import log_activity

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')


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
