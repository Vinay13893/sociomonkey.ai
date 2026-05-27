from flask import Blueprint, jsonify, request

from app.middleware import require_auth, require_role
from app.models.base import db
from app.models.user import User
from app.utils.jwt import hash_password
from app.utils.activity import log_activity

team_bp = Blueprint('team', __name__, url_prefix='/api/users')


@team_bp.route('', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def get_users():
    user = request.current_user
    tid  = request.current_tenant_id
    if user.role == 'superadmin':
        users = User.query.filter_by(is_active=True, tenant_id=tid).all()
    else:
        users = [u for u in user.team_members if u.is_active and u.tenant_id == tid]
    return jsonify({'users': [u.to_dict() for u in users]}), 200


@team_bp.route('', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def create_user():
    user = request.current_user
    data = request.get_json() or {}

    email = data.get('email', '').strip()
    name = data.get('name', '').strip()
    if not email or not name:
        return jsonify({'error': 'Email and name are required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already in use'}), 400

    role = data.get('role', 'team_member')
    if user.role == 'sales_manager' and role != 'team_member':
        return jsonify({'error': 'Sales managers can only create team members'}), 403

    new_user = User(
        name=name,
        email=email,
        phone=data.get('phone'),
        password_hash=hash_password(data.get('password', 'TeamMember@123')),
        role=role,
        tenant_id=user.tenant_id,
        manager_id=user.id if user.role == 'sales_manager' else None,
        is_active=True,
    )
    db.session.add(new_user)
    db.session.commit()

    log_activity(
        user.id, 'create_user', 'users', new_user.id, 'User',
        description=f'Created user {new_user.email}',
    )
    return jsonify({'user': new_user.to_dict()}), 201


@team_bp.route('/<int:user_id>', methods=['GET'])
@require_auth
def get_user(user_id):
    user = User.query.get_or_404(user_id, description='User not found')
    return jsonify({'user': user.to_dict()}), 200


@team_bp.route('/<int:user_id>', methods=['PUT'])
@require_role('superadmin', 'sales_manager')
def update_user(user_id):
    current_user = request.current_user
    target = User.query.get(user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    if current_user.role == 'sales_manager' and target.manager_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json() or {}
    old_data = target.to_dict()

    target.name = data.get('name', target.name)
    target.phone = data.get('phone', target.phone)
    target.is_active = data.get('is_active', target.is_active)
    if data.get('password'):
        target.password_hash = hash_password(data['password'])
    if 'role' in data and current_user.role == 'superadmin':
        target.role = data['role']
    if 'manager_id' in data and current_user.role == 'superadmin':
        new_manager_id = data.get('manager_id')
        if new_manager_id:
            manager = User.query.get(new_manager_id)
            if not manager or manager.role != 'sales_manager':
                return jsonify({'error': 'Invalid sales manager'}), 400
        target.manager_id = new_manager_id
    new_email = data.get('email', '').strip()
    if new_email and new_email != target.email:
        if User.query.filter(User.email == new_email, User.id != target.id).first():
            return jsonify({'error': 'Email already in use by another account'}), 400
        target.email = new_email

    db.session.commit()

    log_activity(
        current_user.id, 'update_user', 'users', user_id, 'User',
        old_value=old_data, new_value=target.to_dict(),
        description=f'Updated user {target.email}',
    )
    return jsonify({'user': target.to_dict()}), 200


@team_bp.route('/<int:user_id>', methods=['DELETE'])
@require_role('superadmin', 'sales_manager')
def delete_user(user_id):
    current_user = request.current_user
    target = User.query.get(user_id)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    if target.id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    if current_user.role == 'sales_manager' and target.manager_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403

    target.is_active = False
    db.session.commit()

    log_activity(
        current_user.id, 'delete_user', 'users', user_id, 'User',
        description=f'Deleted user {target.email}',
    )
    return jsonify({'message': 'User deleted'}), 200


@team_bp.route('/<int:user_id>/team', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def get_user_team(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'team_members': [u.to_dict() for u in user.team_members]}), 200
