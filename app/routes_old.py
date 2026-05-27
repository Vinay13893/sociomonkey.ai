from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import User, Project, Lead
from app.auth import hash_password, check_password, create_token, decode_token
from functools import wraps

bp = Blueprint('api', __name__, url_prefix='/api')

# --- helpers ---
def get_auth_user():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    token = auth.split(' ', 1)[1]
    data = decode_token(token)
    if not data:
        return None
    return User.query.get(data.get('sub'))

def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_auth_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        request.current_user = user
        return func(*args, **kwargs)
    return wrapper

def require_role(*roles):
    def deco(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = get_auth_user()
            if not user or user.role not in roles:
                return jsonify({'error': 'Permission denied'}), 403
            request.current_user = user
            return func(*args, **kwargs)
        return wrapper
    return deco

# --- auth routes ---
@bp.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    email = data.get('email')
    name = data.get('name')
    password = data.get('password')
    role = data.get('role', 'sales')

    if not email or not password or not name:
        return jsonify({'error': 'name, email and password required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400

    user = User(name=name, email=email, password_hash=hash_password(password), role=role)
    db.session.add(user)
    db.session.commit()
    return jsonify({'user': user.to_dict()}), 201

@bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not check_password(password, user.password_hash):
        return jsonify({'error': 'Invalid credentials'}), 401

    token = create_token(user.id, user.role)
    return jsonify({'token': token, 'user': user.to_dict()}), 200

@bp.route('/auth/me', methods=['GET'])
@require_auth
def me():
    user = request.current_user
    return jsonify({'user': user.to_dict()}), 200

# --- projects ---
@bp.route('/projects', methods=['GET'])
@require_auth
def get_projects():
    projects = Project.query.filter_by(is_active=True).all()
    return jsonify({'projects': [p.to_dict() for p in projects]}), 200

@bp.route('/projects', methods=['POST'])
@require_role('admin', 'superadmin', 'sales')
def create_project():
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({'error': 'name required'}), 400
    if Project.query.filter_by(name=name).first():
        return jsonify({'error': 'project exists'}), 400
    p = Project(
        name=name,
        description=data.get('description'),
        location=data.get('location'),
        developer=data.get('developer'),
        project_type=data.get('project_type'),
        budget_min=data.get('budget_min'),
        budget_max=data.get('budget_max')
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'project': p.to_dict()}), 201

@bp.route('/projects/<int:project_id>', methods=['PUT'])
@require_role('admin', 'superadmin', 'sales')
def update_project(project_id):
    p = Project.query.get(project_id)
    if not p:
        return jsonify({'error': 'not found'}), 404
    data = request.get_json() or {}
    p.name = data.get('name', p.name)
    p.description = data.get('description', p.description)
    p.location = data.get('location', p.location)
    p.developer = data.get('developer', p.developer)
    p.project_type = data.get('project_type', p.project_type)
    p.budget_min = data.get('budget_min', p.budget_min)
    p.budget_max = data.get('budget_max', p.budget_max)
    db.session.commit()
    return jsonify({'project': p.to_dict()}), 200

# --- leads ---
@bp.route('/leads', methods=['GET'])
@require_auth
def get_leads():
    project_id = request.args.get('project_id')
    q = Lead.query
    if project_id:
        q = q.filter_by(project_id=project_id)
    leads = q.order_by(Lead.created_at.desc()).all()
    return jsonify({'leads': [l.to_dict() for l in leads]}), 200

@bp.route('/leads', methods=['POST'])
@require_role('sales','telecaller','admin','superadmin')
def create_lead():
    data = request.get_json() or {}
    name = data.get('name')
    if not name:
        return jsonify({'error':'name required'}), 400
    lead = Lead(
        name=name,
        phone=data.get('phone'),
        email=data.get('email'),
        source=data.get('source'),
        budget_min=data.get('budget_min'),
        budget_max=data.get('budget_max'),
        project_id=data.get('project_id'),
        status=data.get('status','new'),
        assigned_to=data.get('assigned_to')
    )
    db.session.add(lead)
    db.session.commit()
    return jsonify({'lead': lead.to_dict()}), 201

@bp.route('/leads/<int:lead_id>', methods=['PUT'])
@require_role('sales','telecaller','admin','superadmin')
def update_lead(lead_id):
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error':'not found'}), 404
    data = request.get_json() or {}
    lead.name = data.get('name', lead.name)
    lead.phone = data.get('phone', lead.phone)
    lead.email = data.get('email', lead.email)
    lead.status = data.get('status', lead.status)
    lead.assigned_to = data.get('assigned_to', lead.assigned_to)
    db.session.commit()
    return jsonify({'lead': lead.to_dict()}), 200
