from flask import Blueprint, request, jsonify, current_app, send_file, Response
from app import db
from app.models import (
    User, Project, Lead, ActivityLog, StatusHistory, 
    LeadNote, LeadAssignmentHistory, Role
)
from app.auth import hash_password, check_password, create_token, decode_token
from functools import wraps
from datetime import datetime
import pandas as pd
from io import BytesIO
import os

print("[DEBUG] routes.py module loaded - version with Excel endpoints")

bp = Blueprint('api', __name__, url_prefix='/api')

# =============================================================================
# HELPERS & MIDDLEWARE
# =============================================================================

def get_auth_user():
    """Extract and validate JWT token, return User object"""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    token = auth.split(' ', 1)[1]
    data = decode_token(token)
    if not data:
        return None
    return User.query.get(data.get('sub'))

def require_auth(func):
    """Decorator: Require authentication"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_auth_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        request.current_user = user
        return func(*args, **kwargs)
    return wrapper

def require_role(*roles):
    """Decorator: Require specific role(s)"""
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

def log_activity(user_id, action, module, resource_id=None, resource_type=None, 
                 old_value=None, new_value=None, description=None):
    """Log an activity to the database"""
    log = ActivityLog(
        user_id=user_id,
        action=action,
        module=module,
        resource_id=resource_id,
        resource_type=resource_type,
        old_value=old_value,
        new_value=new_value,
        description=description,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()

def get_user_visible_leads(user):
    """Get leads visible to user based on role hierarchy"""
    if user.role == 'superadmin':
        return Lead.query
    elif user.role == 'sales_manager':
        # Can see leads assigned to them and their team members
        team_member_ids = [tm.id for tm in user.team_members]
        return Lead.query.filter(
            (Lead.assigned_to == user.id) | 
            (Lead.assigned_to.in_(team_member_ids))
        )
    elif user.role == 'team_member':
        # Can only see leads assigned to them
        return Lead.query.filter(Lead.assigned_to == user.id)
    return Lead.query.filter(Lead.id == -1)  # Return empty

# =============================================================================
# AUTHENTICATION ROUTES
# =============================================================================

@bp.route('/auth/login', methods=['POST'])
def login():
    """Login user with email and password"""
    data = request.get_json() or {}
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()
    if not user or not check_password(password, user.password_hash):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is inactive'}), 403

    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()

    token = create_token(user.id, user.role)
    log_activity(user.id, 'login', 'auth', description=f'{user.email} logged in')
    
    return jsonify({'token': token, 'user': user.to_dict()}), 200

@bp.route('/auth/me', methods=['GET'])
@require_auth
def me():
    """Get current user info"""
    user = request.current_user
    return jsonify({'user': user.to_dict()}), 200

@bp.route('/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Logout current user"""
    user = request.current_user
    log_activity(user.id, 'logout', 'auth', description=f'{user.email} logged out')
    return jsonify({'message': 'Logged out successfully'}), 200

# =============================================================================
# USERS / TEAM MANAGEMENT
# =============================================================================

@bp.route('/users', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def get_users():
    """Get list of users (filtered by role)"""
    user = request.current_user
    
    if user.role == 'superadmin':
        users = User.query.all()
    else:
        # Sales manager can see their team members
        users = user.team_members
    
    return jsonify({'users': [u.to_dict() for u in users]}), 200

@bp.route('/users', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def create_user():
    """Create a new user"""
    user = request.current_user
    data = request.get_json() or {}
    
    email = data.get('email')
    name = data.get('name')
    password = data.get('password', 'TeamMember@123')
    role = data.get('role', 'team_member')
    phone = data.get('phone')
    
    if not email or not name:
        return jsonify({'error': 'Email and name required'}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    # Sales manager can only create team members
    if user.role == 'sales_manager' and role != 'team_member':
        return jsonify({'error': 'Can only create team members'}), 403
    
    new_user = User(
        name=name,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        role=role,
        manager_id=user.id if user.role == 'sales_manager' else None,
        is_active=True
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    log_activity(user.id, 'create_user', 'users', new_user.id, 'User', 
                 description=f'Created user {new_user.email}')
    
    return jsonify({'user': new_user.to_dict()}), 201

@bp.route('/users/<int:user_id>', methods=['PUT'])
@require_role('superadmin', 'sales_manager')
def update_user(user_id):
    """Update user details"""
    current_user = request.current_user
    target_user = User.query.get(user_id)
    
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Sales manager can only edit their team members
    if current_user.role == 'sales_manager' and target_user.manager_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json() or {}
    
    old_data = target_user.to_dict()
    
    target_user.name = data.get('name', target_user.name)
    target_user.phone = data.get('phone', target_user.phone)
    target_user.is_active = data.get('is_active', target_user.is_active)
    
    if 'password' in data and data['password']:
        target_user.password_hash = hash_password(data['password'])
    
    db.session.commit()
    
    log_activity(current_user.id, 'update_user', 'users', user_id, 'User',
                 old_value=old_data, new_value=target_user.to_dict(),
                 description=f'Updated user {target_user.email}')
    
    return jsonify({'user': target_user.to_dict()}), 200

@bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_role('superadmin', 'sales_manager')
def delete_user(user_id):
    """Soft-delete a user (deactivate)"""
    current_user = request.current_user
    target_user = User.query.get(user_id)
    
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    if target_user.id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    # Sales manager can only delete their own team members
    if current_user.role == 'sales_manager' and target_user.manager_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    target_user.is_active = False
    db.session.commit()
    
    log_activity(current_user.id, 'delete_user', 'users', user_id, 'User',
                 description=f'Deleted user {target_user.email}')
    
    return jsonify({'message': 'User deleted'}), 200

@bp.route('/users/<int:user_id>', methods=['GET'])
@require_auth
def get_user(user_id):
    """Get specific user details"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200

@bp.route('/users/<int:user_id>/team', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def get_user_team(user_id):
    """Get team members under a user"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({'team_members': [u.to_dict() for u in user.team_members]}), 200

# =============================================================================
# PROJECTS
# =============================================================================

@bp.route('/projects', methods=['GET'])
@require_auth
def get_projects():
    """Get all active projects"""
    projects = Project.query.filter_by(is_active=True).all()
    return jsonify({'projects': [p.to_dict() for p in projects]}), 200

@bp.route('/projects', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def create_project():
    """Create new project"""
    user = request.current_user
    data = request.get_json() or {}
    name = data.get('name')
    
    if not name:
        return jsonify({'error': 'Project name required'}), 400
    
    if Project.query.filter_by(name=name).first():
        return jsonify({'error': 'Project already exists'}), 400
    
    project = Project(
        name=name,
        description=data.get('description'),
        location=data.get('location'),
        developer=data.get('developer'),
        project_type=data.get('project_type'),
        budget_min=data.get('budget_min'),
        budget_max=data.get('budget_max'),
        created_by=user.id
    )
    
    db.session.add(project)
    db.session.commit()
    
    log_activity(user.id, 'create_project', 'projects', project.id, 'Project',
                 description=f'Created project {project.name}')
    
    return jsonify({'project': project.to_dict()}), 201

@bp.route('/projects/<int:project_id>', methods=['PUT'])
@require_role('superadmin', 'sales_manager')
def update_project(project_id):
    """Update project details"""
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
    
    log_activity(user.id, 'update_project', 'projects', project_id, 'Project',
                 old_value=old_data, new_value=project.to_dict(),
                 description=f'Updated project {project.name}')
    
    return jsonify({'project': project.to_dict()}), 200

@bp.route('/projects/<int:project_id>', methods=['DELETE'])
@require_role('superadmin', 'sales_manager')
def delete_project(project_id):
    """Soft-delete a project"""
    user = request.current_user
    project = Project.query.get(project_id)
    
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    project.is_active = False
    db.session.commit()
    
    log_activity(user.id, 'delete_project', 'projects', project_id, 'Project',
                 description=f'Deleted project {project.name}')
    
    return jsonify({'message': 'Project deleted'}), 200

# =============================================================================
# LEADS
# =============================================================================

@bp.route('/leads', methods=['GET'])
@require_auth
def get_leads():
    """Get leads visible to current user based on role"""
    user = request.current_user
    
    # Get filtered leads
    query = get_user_visible_leads(user)
    
    # Apply additional filters
    project_id = request.args.get('project_id')
    status = request.args.get('status')
    
    if project_id:
        query = query.filter_by(project_id=project_id)
    if status:
        query = query.filter_by(status=status)
    
    leads = query.order_by(Lead.created_at.desc()).all()
    return jsonify({'leads': [l.to_dict() for l in leads]}), 200

@bp.route('/leads', methods=['POST'])
@require_role('superadmin', 'sales_manager', 'team_member')
def create_lead():
    """Create new lead"""
    user = request.current_user
    data = request.get_json() or {}
    name = data.get('name')
    
    if not name:
        return jsonify({'error': 'Lead name required'}), 400

    # Duplicate phone check (skip if force=true passed)
    phone_val = (data.get('phone') or '').strip()
    if phone_val and not data.get('force'):
        existing = Lead.query.filter(Lead.phone == phone_val).first()
        if existing:
            return jsonify({
                'error': 'duplicate_phone',
                'message': 'A lead with this phone number already exists.',
                'existing_lead': {
                    'id': existing.id,
                    'name': existing.name,
                    'phone': existing.phone,
                    'status': existing.status
                }
            }), 409

    lead = Lead(
        name=name,
        phone=data.get('phone'),
        email=data.get('email'),
        source=data.get('source'),
        budget_min=data.get('budget_min'),
        budget_max=data.get('budget_max'),
        project_id=data.get('project_id'),
        status=data.get('status', 'new'),
        created_by=user.id
    )
    
    db.session.add(lead)
    db.session.commit()
    
    log_activity(user.id, 'create_lead', 'leads', lead.id, 'Lead',
                 description=f'Created lead {lead.name}')
    
    return jsonify({'lead': lead.to_dict()}), 201

@bp.route('/leads/<int:lead_id>', methods=['GET'])
@require_auth
def get_lead(lead_id):
    """Get specific lead with permissions check"""
    user = request.current_user
    lead = Lead.query.get(lead_id)
    
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    # Check visibility
    if user.role == 'team_member' and lead.assigned_to != user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    if user.role == 'sales_manager':
        team_ids = [tm.id for tm in user.team_members]
        if lead.assigned_to not in team_ids and lead.assigned_to != user.id:
            return jsonify({'error': 'Permission denied'}), 403
    
    return jsonify({'lead': lead.to_dict()}), 200

@bp.route('/leads/<int:lead_id>', methods=['PUT'])
@require_auth
def update_lead(lead_id):
    """Update lead details with status history tracking"""
    user = request.current_user
    lead = Lead.query.get(lead_id)
    
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    # Check permissions
    if user.role == 'team_member' and lead.assigned_to != user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    data = request.get_json() or {}
    
    old_data = lead.to_dict()
    old_status = lead.status
    
    lead.name = data.get('name', lead.name)
    lead.phone = data.get('phone', lead.phone)
    lead.email = data.get('email', lead.email)
    
    # Update status and track history
    new_status = data.get('status')
    if new_status and new_status != old_status:
        lead.status = new_status
        
        # Create status history entry
        status_history = StatusHistory(
            lead_id=lead_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=user.id
        )
        db.session.add(status_history)
    
    db.session.commit()
    
    log_activity(user.id, 'update_lead', 'leads', lead_id, 'Lead',
                 old_value=old_data, new_value=lead.to_dict(),
                 description=f'Updated lead {lead.name}')
    
    return jsonify({'lead': lead.to_dict()}), 200

@bp.route('/leads/<int:lead_id>/assign', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def assign_lead(lead_id):
    """Assign lead to team member"""
    user = request.current_user
    lead = Lead.query.get(lead_id)
    
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    data = request.get_json() or {}
    assigned_to = data.get('assigned_to')
    reason = data.get('reason')
    
    if not assigned_to:
        return jsonify({'error': 'assigned_to required'}), 400
    
    target_user = User.query.get(assigned_to)
    if not target_user:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if user can assign to this person
    if user.role == 'sales_manager':
        if target_user.manager_id != user.id:
            return jsonify({'error': 'Can only assign to own team'}), 403
    
    # Create assignment history
    assignment = LeadAssignmentHistory(
        lead_id=lead_id,
        assigned_from=lead.assigned_to,
        assigned_to=assigned_to,
        assigned_by=user.id,
        reason=reason
    )
    
    old_assigned = lead.assigned_to
    lead.assigned_to = assigned_to
    lead.assigned_by = user.id
    
    db.session.add(assignment)
    db.session.commit()
    
    old_user_name = User.query.get(old_assigned).name if old_assigned else 'Unassigned'
    log_activity(user.id, 'assign_lead', 'leads', lead_id, 'Lead',
                 description=f'Assigned lead {lead.name} from {old_user_name} to {target_user.name}')
    
    return jsonify({'lead': lead.to_dict(), 'assignment': assignment.to_dict()}), 200

@bp.route('/leads/<int:lead_id>/status-history', methods=['GET'])
@require_auth
def get_status_history(lead_id):
    """Get status change history for a lead"""
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    history = StatusHistory.query.filter_by(lead_id=lead_id).order_by(StatusHistory.changed_at.desc()).all()
    return jsonify({'status_history': [h.to_dict() for h in history]}), 200

@bp.route('/leads/<int:lead_id>/assignment-history', methods=['GET'])
@require_auth
def get_assignment_history(lead_id):
    """Get assignment history for a lead"""
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    history = LeadAssignmentHistory.query.filter_by(lead_id=lead_id).order_by(LeadAssignmentHistory.assigned_at.desc()).all()
    return jsonify({'assignment_history': [h.to_dict() for h in history]}), 200

# =============================================================================
# LEAD NOTES
# =============================================================================

@bp.route('/leads/<int:lead_id>/notes', methods=['GET'])
@require_auth
def get_lead_notes(lead_id):
    """Get notes for a lead"""
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    notes = LeadNote.query.filter_by(lead_id=lead_id).order_by(LeadNote.created_at.desc()).all()
    return jsonify({'notes': [n.to_dict() for n in notes]}), 200

@bp.route('/leads/<int:lead_id>/notes', methods=['POST'])
@require_auth
def add_lead_note(lead_id):
    """Add a note to a lead"""
    user = request.current_user
    lead = Lead.query.get(lead_id)
    
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    
    data = request.get_json() or {}
    note_text = data.get('note')
    
    if not note_text:
        return jsonify({'error': 'Note text required'}), 400
    
    note = LeadNote(
        lead_id=lead_id,
        note=note_text,
        created_by=user.id
    )
    
    db.session.add(note)
    db.session.commit()
    
    log_activity(user.id, 'add_note', 'leads', lead_id, 'LeadNote',
                 description=f'Added note to lead {lead.name}')
    
    return jsonify({'note': note.to_dict()}), 201

# =============================================================================
# ACTIVITY LOGS (Admin Only)
# =============================================================================

@bp.route('/activity-logs', methods=['GET'])
@require_role('superadmin')
def get_activity_logs():
    """Get all activity logs (admin only)"""
    user_id = request.args.get('user_id')
    action = request.args.get('action')
    module = request.args.get('module')
    limit = request.args.get('limit', 100, type=int)
    
    query = ActivityLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter_by(action=action)
    if module:
        query = query.filter_by(module=module)
    
    logs = query.order_by(ActivityLog.created_at.desc()).limit(limit).all()
    return jsonify({'activity_logs': [l.to_dict() for l in logs]}), 200

# =============================================================================
# DASHBOARD STATS
# =============================================================================

@bp.route('/dashboard/stats', methods=['GET'])
@require_auth
def dashboard_stats():
    """Get dashboard statistics based on user role"""
    user = request.current_user
    
    if user.role == 'superadmin':
        total_leads = Lead.query.count()
        total_users = User.query.count()
        total_projects = Project.query.count()
        
        status_counts = {}
        for status in ['new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
                       'site_visit_planned', 'site_visit_done', 'negotiation',
                       'booking_done', 'not_interested', 'lost', 'junk']:
            status_counts[status] = Lead.query.filter_by(status=status).count()
        
        stats = {
            'total_leads': total_leads,
            'total_users': total_users,
            'total_projects': total_projects,
            'status_counts': status_counts
        }
    
    elif user.role == 'sales_manager':
        team_ids = [tm.id for tm in user.team_members]
        team_ids.append(user.id)
        
        total_leads = Lead.query.filter(Lead.assigned_to.in_(team_ids)).count()
        team_size = len(user.team_members)
        
        status_counts = {}
        for status in ['new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
                       'site_visit_planned', 'site_visit_done', 'negotiation',
                       'booking_done', 'not_interested', 'lost', 'junk']:
            status_counts[status] = Lead.query.filter(
                (Lead.assigned_to.in_(team_ids)) & (Lead.status == status)
            ).count()
        
        stats = {
            'my_leads': total_leads,
            'team_size': team_size,
            'status_counts': status_counts
        }
    
    else:  # Team member
        my_leads = Lead.query.filter_by(assigned_to=user.id).count()
        
        status_counts = {}
        for status in ['new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
                       'site_visit_planned', 'site_visit_done', 'negotiation',
                       'booking_done', 'not_interested', 'lost', 'junk']:
            status_counts[status] = Lead.query.filter_by(
                assigned_to=user.id, status=status
            ).count()
        
        stats = {
            'my_leads': my_leads,
            'status_counts': status_counts
        }
    
    return jsonify({'stats': stats}), 200

# =============================================================================
# PIPELINE / KANBAN
# =============================================================================

@bp.route('/pipeline/stages', methods=['GET'])
@require_auth
def get_pipeline_stages():
    """Get leads grouped by status (pipeline view)"""
    user = request.current_user
    
    stages = ['new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
              'site_visit_planned', 'site_visit_done', 'negotiation',
              'booking_done', 'not_interested', 'lost', 'junk']
    
    pipeline = {}
    
    for stage in stages:
        query = get_user_visible_leads(user).filter_by(status=stage)
        leads = query.all()
        pipeline[stage] = {
            'count': len(leads),
            'leads': [l.to_dict() for l in leads]
        }
    
    return jsonify({'pipeline': pipeline}), 200


# =============================================================================
# EXCEL UPLOAD
# =============================================================================

@bp.route('/leads/import/excel', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def import_leads_excel():
    """
    Bulk import leads from Excel file.
    
    Expected Excel columns:
    - name (required)
    - phone (optional)
    - email (optional)
    - source (optional)
    - budget_min (optional)
    - budget_max (optional)
    - project_id (optional)
    - status (optional, defaults to 'new')
    - assigned_to_email (optional, email of team member)
    
    Returns:
    {
        'success': int,
        'failed': int,
        'total': int,
        'imported_leads': [lead objects],
        'errors': [{'row': n, 'error': 'message'}]
    }
    """
    user = request.current_user
    
    # Check for file
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file extension
    allowed_ext = ['.xlsx', '.xls', '.csv']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_ext:
        return jsonify({'error': f'File type not allowed. Use {", ".join(allowed_ext)}'}), 400
    
    try:
        # Read Excel file
        if file_ext == '.csv':
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Required column: name
        if 'name' not in df.columns:
            return jsonify({'error': 'Excel file must contain a "name" column'}), 400
        
        # Normalize column names to lowercase
        df.columns = df.columns.str.lower().str.strip()

        # --- Pre-build set of all phones in this file (normalised) ---
        def _norm_phone(raw):
            if pd.isna(raw):
                return None
            s = str(raw).strip()
            if not s or s == 'nan':
                return None
            if s.endswith('.0') and s[:-2].isdigit():
                s = s[:-2]
            return s or None

        file_phones = set()
        for _, frow in df.iterrows():
            p = _norm_phone(frow.get('phone'))
            if p:
                file_phones.add(p)

        # Single DB query: fetch all leads whose phone matches any in this file
        existing_phone_map = {}  # phone -> Lead
        if file_phones:
            existing_leads = Lead.query.filter(Lead.phone.in_(list(file_phones))).all()
            for el in existing_leads:
                existing_phone_map[el.phone] = el

        # Track results
        imported_leads = []
        errors = []
        seen_phones = set()  # phones added in this batch (in-memory)

        # Process each row
        for idx, row in df.iterrows():
            row_num = idx + 2  # +2: 0-indexed + 1 for header
            
            try:
                # Validate required field
                name = str(row.get('name', '')).strip()
                if not name or name == 'nan':
                    errors.append({'row': row_num, 'error': 'Name is required'})
                    continue
                
                # Extract optional fields
                phone = _norm_phone(row.get('phone'))
                email = str(row.get('email', '')).strip() if pd.notna(row.get('email')) else None

                # Skip duplicate phones (already in DB or earlier in this batch)
                if phone:
                    if phone in seen_phones:
                        errors.append({'row': row_num, 'error': f'Duplicate phone {phone} in this file'})
                        continue
                    if phone in existing_phone_map:
                        ex = existing_phone_map[phone]
                        errors.append({'row': row_num, 'error': f'Duplicate: phone {phone} already exists (lead "{ex.name}" ID #{ex.id})'})
                        continue
                    seen_phones.add(phone)

                source = str(row.get('source', 'direct')).strip() if pd.notna(row.get('source')) else 'direct'
                status = str(row.get('status', 'new')).strip() if pd.notna(row.get('status')) else 'new'
                
                # Remap legacy status names to new names (backward compat for old exports)
                _status_aliases = {'attempted': 'no_answer', 'connected': 'follow_up'}
                status = _status_aliases.get(status, status)

                # Validate status
                valid_statuses = ['new', 'no_answer', 'follow_up', 'callback_scheduled',
                                  'interested', 'site_visit_planned', 'site_visit_done',
                                  'negotiation', 'booking_done',
                                  'not_interested', 'lost', 'junk']
                if status not in valid_statuses:
                    status = 'new'
                
                # Budget fields
                budget_min = None
                budget_max = None
                try:
                    if pd.notna(row.get('budget_min')):
                        budget_min = float(row.get('budget_min'))
                    if pd.notna(row.get('budget_max')):
                        budget_max = float(row.get('budget_max'))
                except (ValueError, TypeError):
                    pass
                
                # Project assignment
                project_id = None
                if pd.notna(row.get('project_id')):
                    try:
                        project_id = int(row.get('project_id'))
                        # Verify project exists and belongs to same company
                        project = Project.query.get(project_id)
                        if not project:
                            errors.append({'row': row_num, 'error': f'Project ID {project_id} not found'})
                            continue
                    except (ValueError, TypeError):
                        errors.append({'row': row_num, 'error': f'Invalid project ID'})
                        continue
                
                # Lead assignment
                assigned_to_id = None
                if pd.notna(row.get('assigned_to_email')):
                    assigned_email = str(row.get('assigned_to_email')).strip()
                    assigned_user = User.query.filter_by(email=assigned_email).first()
                    if not assigned_user:
                        errors.append({'row': row_num, 'error': f'User with email {assigned_email} not found'})
                        continue
                    
                    # For managers, verify they're assigning to their own team
                    if user.role == 'sales_manager':
                        if assigned_user.manager_id != user.id:
                            errors.append({'row': row_num, 'error': f'You can only assign to your own team'})
                            continue
                    
                    assigned_to_id = assigned_user.id
                
                # Create lead
                lead = Lead(
                    name=name,
                    phone=phone,
                    email=email,
                    source=source,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    project_id=project_id,
                    status=status,
                    assigned_to=assigned_to_id,
                    assigned_by=user.id if assigned_to_id else None,
                    created_by=user.id
                )
                
                db.session.add(lead)
                db.session.flush()  # Get lead ID for activity log
                
                # Log activity
                log_activity(
                    user_id=user.id,
                    action='create',
                    module='lead',
                    resource_id=lead.id,
                    resource_type='Lead',
                    new_value={'name': name, 'source': source},
                    description=f'Lead imported from Excel: {name}'
                )
                
                imported_leads.append(lead.to_dict())
                
            except Exception as e:
                errors.append({'row': row_num, 'error': str(e)})
        
        # Commit all changes
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Database error: {str(e)}'}), 500
        
        return jsonify({
            'success': len(imported_leads),
            'failed': len(errors),
            'total': len(df),
            'imported_leads': imported_leads,
            'errors': errors
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


@bp.route('/template', methods=['GET'])
def get_import_template():
    """Get a template Excel file for bulk lead import."""
    return jsonify({'message': 'template endpoint works'}), 200


# =============================================================================
# EXPORT & REPORTING
# =============================================================================

@bp.route('/export', methods=['GET'])
def export_leads_excel():
    """Export leads to Excel file."""
    return jsonify({'message': 'export endpoint works'}), 200


@bp.route('/reports/leads', methods=['GET'])
def get_lead_reports():
    """
    Get comprehensive lead reports and analytics.
    
    Returns:
    {
        'total_leads': int,
        'leads_by_status': {status: count},
        'leads_by_source': {source: count},
        'leads_by_project': {project: count},
        'conversion_rate': float,
        'avg_days_to_conversion': float,
        'leads_by_date': {date: count},
        'team_performance': {user_name: stats}
    }
    """
    user = request.current_user
    
    # Get all visible leads
    leads = get_user_visible_leads(user).all()
    
    # Basic stats
    total_leads = len(leads)
    
    # By status
    status_counts = {}
    for lead in leads:
        status = lead.status or 'unknown'
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # By source
    source_counts = {}
    for lead in leads:
        source = lead.source or 'unknown'
        source_counts[source] = source_counts.get(source, 0) + 1
    
    # By project
    project_counts = {}
    for lead in leads:
        if lead.project:
            project_name = lead.project.name
            project_counts[project_name] = project_counts.get(project_name, 0) + 1
    
    # Conversion metrics
    converted_statuses = ['booking_done', 'negotiation']
    converted_leads = [l for l in leads if l.status in converted_statuses]
    conversion_rate = (len(converted_leads) / total_leads * 100) if total_leads > 0 else 0
    
    # Conversion time
    conversion_times = []
    for lead in converted_leads:
        if lead.created_at:
            status_history = StatusHistory.query.filter_by(lead_id=lead.id).order_by(
                StatusHistory.changed_at.desc()
            ).first()
            if status_history:
                time_diff = (status_history.changed_at - lead.created_at).days
                conversion_times.append(time_diff)
    
    avg_conversion_time = sum(conversion_times) / len(conversion_times) if conversion_times else 0
    
    # By date
    date_counts = {}
    for lead in leads:
        if lead.created_at:
            date_str = lead.created_at.strftime('%Y-%m-%d')
            date_counts[date_str] = date_counts.get(date_str, 0) + 1
    
    # Team performance
    team_performance = {}
    for lead in leads:
        if lead.assigned_to_user:
            user_name = lead.assigned_to_user.name
            if user_name not in team_performance:
                team_performance[user_name] = {
                    'total_leads': 0,
                    'converted': 0,
                    'in_progress': 0,
                    'lost': 0
                }
            
            team_performance[user_name]['total_leads'] += 1
            
            if lead.status in converted_statuses:
                team_performance[user_name]['converted'] += 1
            elif lead.status == 'lost':
                team_performance[user_name]['lost'] += 1
            else:
                team_performance[user_name]['in_progress'] += 1
    
    # Add conversion rates per user
    for user_name, stats in team_performance.items():
        total = stats['total_leads']
        stats['conversion_rate'] = (stats['converted'] / total * 100) if total > 0 else 0
    
    return jsonify({
        'total_leads': total_leads,
        'leads_by_status': status_counts,
        'leads_by_source': source_counts,
        'leads_by_project': project_counts,
        'conversion_rate': round(conversion_rate, 2),
        'avg_days_to_conversion': round(avg_conversion_time, 1),
        'leads_by_date': date_counts,
        'team_performance': team_performance
    }), 200


@bp.route('/reports/team', methods=['GET'])
def get_team_reports():
    """
    Get team performance reports.
    
    Returns: Team statistics including lead counts, conversion rates, etc.
    """
    user = request.current_user
    
    # Get all visible users
    if user.role == 'superadmin':
        users = User.query.all()
    elif user.role == 'sales_manager':
        users = User.query.filter(
            (User.manager_id == user.id) | (User.id == user.id)
        ).all()
    else:
        users = [user]
    
    team_stats = {}
    
    for u in users:
        user_leads = Lead.query.filter_by(assigned_to=u.id).all()
        
        converted = len([l for l in user_leads if l.status in ['booking_done', 'negotiation']])
        lost = len([l for l in user_leads if l.status == 'lost'])
        in_progress = len(user_leads) - converted - lost
        
        conversion_rate = (converted / len(user_leads) * 100) if user_leads else 0
        
        team_stats[u.name] = {
            'email': u.email,
            'role': u.role,
            'total_leads': len(user_leads),
            'converted': converted,
            'in_progress': in_progress,
            'lost': lost,
            'conversion_rate': round(conversion_rate, 2),
            'last_activity': u.last_login.isoformat() if u.last_login else None
        }
    
    return jsonify({'team_statistics': team_stats}), 200


@bp.route('/reports/activity', methods=['GET'])
def get_activity_reports():
    """
    Get activity reports for admin users only.
    
    Returns: Activity statistics by user, action, and module
    """
    
    # Activity by user
    user_activity = {}
    for log in ActivityLog.query.all():
        user_name = User.query.get(log.user_id).name if log.user_id else 'Unknown'
        if user_name not in user_activity:
            user_activity[user_name] = 0
        user_activity[user_name] += 1
    
    # Activity by action
    action_activity = {}
    for log in ActivityLog.query.all():
        action = log.action
        if action not in action_activity:
            action_activity[action] = 0
        action_activity[action] += 1
    
    # Activity by module
    module_activity = {}
    for log in ActivityLog.query.all():
        module = log.module
        if module not in module_activity:
            module_activity[module] = 0
        module_activity[module] += 1
    
    # Activity over time (last 7 days)
    from datetime import timedelta
    last_week = datetime.utcnow() - timedelta(days=7)
    recent_activity = ActivityLog.query.filter(ActivityLog.created_at >= last_week).all()
    
    activity_by_date = {}
    for log in recent_activity:
        date_str = log.created_at.strftime('%Y-%m-%d')
        if date_str not in activity_by_date:
            activity_by_date[date_str] = 0
        activity_by_date[date_str] += 1
    
    return jsonify({
        'activity_by_user': user_activity,
        'activity_by_action': action_activity,
        'activity_by_module': module_activity,
        'activity_last_7_days': activity_by_date,
        'total_activities': ActivityLog.query.count()
    }), 200
