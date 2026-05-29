from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta

from sqlalchemy import case, func
from sqlalchemy.orm import selectinload, joinedload

from app.middleware import require_auth, require_role
from app.models.base import db
from app.models.activity import ActivityLog
from app.models.lead import Lead, StatusHistory, LeadNote, LeadAssignmentHistory, CallbackReminder
from app.models.project import Project
from app.models.user import User
from app.utils.activity import log_activity
from app.utils.leads import get_user_visible_leads, VALID_STATUSES

leads_bp = Blueprint('leads', __name__, url_prefix='/api/leads')

CALL_OUTCOME_LABELS = {
    'connected': 'Connected',
    'no_answer': 'No Answer',
    'busy': 'Busy',
    'wrong_number': 'Wrong Number',
    'callback_scheduled': 'Callback Scheduled',
}


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

@leads_bp.route('', methods=['GET'])
@require_auth
def get_leads():
    user = request.current_user
    query = get_user_visible_leads(user)

    project_id = request.args.get('project_id')
    status = request.args.get('status')
    if project_id:
        query = query.filter_by(project_id=int(project_id))
    if status:
        query = query.filter_by(status=status)

    # Eager-load all relationships used by to_dict() to avoid N+1 queries.
    # Without this, each lead triggers separate SELECT for notes, callbacks,
    # and assigned_user.manager — causing thousands of DB round-trips.
    query = query.options(
        selectinload(Lead.notes),
        selectinload(Lead.callbacks),
        joinedload(Lead.assigned_user).joinedload(User.manager),
    )

    leads = query.order_by(Lead.created_at.desc()).all()
    return jsonify({'leads': [l.to_dict() for l in leads]}), 200


@leads_bp.route('', methods=['POST'])
@require_role('superadmin', 'sales_manager', 'team_member')
def create_lead():
    user = request.current_user
    data = request.get_json() or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Lead name is required'}), 400

    phone_val = (data.get('phone') or '').strip()
    if phone_val:
        force = data.get('force') and user.role == 'superadmin'
        if not force:
            existing = Lead.query.filter(
                Lead.phone == phone_val,
                Lead.tenant_id == user.tenant_id,
            ).first()
            if existing:
                return jsonify({
                    'error': 'duplicate_phone',
                    'message': 'A lead with this phone number already exists.',
                    'existing_lead': {
                        'id': existing.id,
                        'name': existing.name,
                        'phone': existing.phone,
                        'status': existing.status,
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
        tenant_id=user.tenant_id,
        created_by=user.id,
    )
    db.session.add(lead)
    db.session.commit()

    log_activity(
        user.id, 'create_lead', 'leads', lead.id, 'Lead',
        description=f'Created lead {lead.name}',
    )
    return jsonify({'lead': lead.to_dict()}), 201


# ---------------------------------------------------------------------------
# Single lead
# ---------------------------------------------------------------------------

@leads_bp.route('/<int:lead_id>', methods=['GET'])
@require_auth
def get_lead(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    if user.role == 'team_member' and lead.assigned_to != user.id:
        return jsonify({'error': 'Permission denied'}), 403
    if user.role == 'sales_manager':
        team_ids = [tm.id for tm in user.team_members]
        if lead.assigned_to not in team_ids and lead.assigned_to != user.id:
            return jsonify({'error': 'Permission denied'}), 403

    return jsonify({'lead': lead.to_dict()}), 200


@leads_bp.route('/<int:lead_id>', methods=['PUT'])
@require_auth
def update_lead(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    if user.role == 'team_member' and lead.assigned_to != user.id:
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json() or {}
    old_data = lead.to_dict()
    old_status = lead.status

    lead.name = data.get('name', lead.name)
    lead.phone = data.get('phone', lead.phone)
    lead.email = data.get('email', lead.email)
    lead.source = data.get('source', lead.source)
    lead.budget_min = data.get('budget_min', lead.budget_min)
    lead.budget_max = data.get('budget_max', lead.budget_max)
    lead.project_id = data.get('project_id', lead.project_id)

    new_status = data.get('status')
    if new_status and new_status != old_status:
        lead.status = new_status
        db.session.add(StatusHistory(
            lead_id=lead_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=user.id,
        ))

    db.session.commit()

    log_activity(
        user.id, 'update_lead', 'leads', lead_id, 'Lead',
        old_value=old_data, new_value=lead.to_dict(),
        description=f'Updated lead {lead.name}',
    )
    return jsonify({'lead': lead.to_dict()}), 200


@leads_bp.route('/<int:lead_id>', methods=['DELETE'])
@require_role('superadmin')
def delete_lead(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    if not lead or not lead.is_active:
        return jsonify({'error': 'Lead not found'}), 404

    if user.role == 'sales_manager':
        team_ids = [tm.id for tm in user.team_members]
        if lead.assigned_to not in team_ids and lead.assigned_to != user.id:
            return jsonify({'error': 'Permission denied'}), 403

    lead.is_active = False
    db.session.commit()
    log_activity(user.id, 'delete_lead', 'leads', lead_id, 'Lead',
                 description=f'Deleted lead {lead.name}')
    return jsonify({'message': 'Lead deleted'}), 200


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------

@leads_bp.route('/bulk-status', methods=['POST'])
@require_auth
def bulk_update_status():
    user = request.current_user
    data = request.get_json() or {}
    lead_ids   = data.get('lead_ids', [])
    new_status = data.get('status')

    if not lead_ids:
        return jsonify({'error': 'lead_ids is required'}), 400
    if not new_status:
        return jsonify({'error': 'status is required'}), 400
    if new_status not in VALID_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(VALID_STATUSES)}'}), 400

    visible_ids = {l.id for l in get_user_visible_leads(user).all()}
    updated = 0
    for lead_id in lead_ids:
        if lead_id not in visible_ids:
            continue
        lead = Lead.query.get(lead_id)
        if not lead:
            continue
        old_status = lead.status
        lead.status = new_status
        history = StatusHistory(
            lead_id=lead_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=user.id,
        )
        db.session.add(history)
        updated += 1

    db.session.commit()
    log_activity(
        user.id, 'bulk_status_update', 'leads', None, 'Lead',
        description=f'Bulk updated {updated} leads to status: {new_status}',
    )
    return jsonify({'updated': updated, 'status': new_status}), 200


@leads_bp.route('/bulk-source', methods=['POST'])
@require_auth
def bulk_update_source():
    user = request.current_user
    data = request.get_json() or {}
    lead_ids   = data.get('lead_ids', [])
    new_source = (data.get('source') or '').strip()

    VALID_SOURCES = ['Website','Referral','Walk-in','Meta','Google',
                     'Email Campaign','Direct','Other','G1','G2','G3','TP']
    if not lead_ids:
        return jsonify({'error': 'lead_ids is required'}), 400
    if not new_source or new_source not in VALID_SOURCES:
        return jsonify({'error': f'Invalid source. Must be one of: {", ".join(VALID_SOURCES)}'}), 400

    visible_ids = {l.id for l in get_user_visible_leads(user).all()}
    updated = 0
    for lead_id in lead_ids:
        if lead_id not in visible_ids:
            continue
        lead = Lead.query.get(lead_id)
        if not lead:
            continue
        lead.source = new_source
        updated += 1

    db.session.commit()
    log_activity(
        user.id, 'bulk_source_update', 'leads', None, 'Lead',
        description=f'Bulk updated {updated} leads to source: {new_source}',
    )
    return jsonify({'updated': updated, 'source': new_source}), 200


@leads_bp.route('/bulk-assign', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def bulk_assign():
    user = request.current_user
    data = request.get_json() or {}
    lead_ids    = data.get('lead_ids', [])
    assigned_to = data.get('assigned_to')  # None means unassign
    assign_type = data.get('assign_type', 'member')  # 'member' or 'manager'

    if not lead_ids:
        return jsonify({'error': 'lead_ids is required'}), 400

    # Validate target user when assigning (not unassigning)
    target_name = 'Unassigned'
    if assigned_to is not None:
        target = User.query.get(assigned_to)
        if not target:
            return jsonify({'error': 'User not found'}), 404
        if assign_type == 'manager' and target.role not in ('sales_manager', 'superadmin'):
            return jsonify({'error': 'Selected user is not a sales manager'}), 400
        if assign_type == 'member' and user.role == 'sales_manager' and target.id != user.id and target.manager_id != user.id:
            return jsonify({'error': 'Can only assign to your own team'}), 403
        target_name = target.name

    updated = 0
    for lead_id in lead_ids:
        lead = Lead.query.get(lead_id)
        if not lead:
            continue
        if assign_type == 'manager':
            lead.sales_manager_id = assigned_to
        else:
            if assigned_to is not None:
                assignment = LeadAssignmentHistory(
                    lead_id=lead_id,
                    assigned_from=lead.assigned_to,
                    assigned_to=assigned_to,
                    assigned_by=user.id,
                )
                db.session.add(assignment)
                lead.assigned_by = user.id
            else:
                lead.assigned_by = None
            lead.assigned_to = assigned_to
        updated += 1

    db.session.commit()
    action = 'bulk_assign_manager' if assign_type == 'manager' else 'bulk_assign'
    log_activity(
        user.id, action, 'leads', None, 'Lead',
        description=f'Bulk assigned {updated} leads to {target_name} ({assign_type})',
    )
    return jsonify({'updated': updated, 'assigned_to_name': target_name}), 200


@leads_bp.route('/bulk-delete', methods=['POST'])
@require_role('superadmin')
def bulk_delete():
    user = request.current_user
    data = request.get_json() or {}
    lead_ids = data.get('lead_ids', [])

    if not lead_ids:
        return jsonify({'error': 'lead_ids is required'}), 400

    visible_ids = {l.id for l in get_user_visible_leads(user).all()}
    deleted = 0
    for lead_id in lead_ids:
        if lead_id not in visible_ids:
            continue
        lead = Lead.query.get(lead_id)
        if not lead or not lead.is_active:
            continue
        lead.is_active = False
        deleted += 1

    db.session.commit()
    log_activity(user.id, 'bulk_delete_leads', 'leads', None, 'Lead',
                 description=f'Bulk deleted {deleted} leads')
    return jsonify({'deleted': deleted}), 200


# Assignment
# ---------------------------------------------------------------------------

@leads_bp.route('/<int:lead_id>/assign', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def assign_lead(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    data = request.get_json() or {}
    assigned_to = data.get('assigned_to')
    if not assigned_to:
        return jsonify({'error': 'assigned_to is required'}), 400

    target = User.query.get(assigned_to)
    if not target:
        return jsonify({'error': 'User not found'}), 404

    if user.role == 'sales_manager' and target.id != user.id and target.manager_id != user.id:
        return jsonify({'error': 'Can only assign to your own team'}), 403

    assignment = LeadAssignmentHistory(
        lead_id=lead_id,
        assigned_from=lead.assigned_to,
        assigned_to=assigned_to,
        assigned_by=user.id,
        reason=data.get('reason'),
    )
    old_name = User.query.get(lead.assigned_to).name if lead.assigned_to else 'Unassigned'
    lead.assigned_to = assigned_to
    lead.assigned_by = user.id
    db.session.add(assignment)
    db.session.commit()

    log_activity(
        user.id, 'assign_lead', 'leads', lead_id, 'Lead',
        description=f'Assigned lead {lead.name} from {old_name} to {target.name}',
    )
    return jsonify({'lead': lead.to_dict(), 'assignment': assignment.to_dict()}), 200


# ---------------------------------------------------------------------------
# Status / assignment history
# ---------------------------------------------------------------------------

@leads_bp.route('/<int:lead_id>/status-history', methods=['GET'])
@require_auth
def get_status_history(lead_id):
    if not Lead.query.get(lead_id):
        return jsonify({'error': 'Lead not found'}), 404
    history = (
        StatusHistory.query
        .filter_by(lead_id=lead_id)
        .order_by(StatusHistory.changed_at.desc())
        .all()
    )
    return jsonify({'status_history': [h.to_dict() for h in history]}), 200


@leads_bp.route('/<int:lead_id>/assignment-history', methods=['GET'])
@require_auth
def get_assignment_history(lead_id):
    if not Lead.query.get(lead_id):
        return jsonify({'error': 'Lead not found'}), 404
    history = (
        LeadAssignmentHistory.query
        .filter_by(lead_id=lead_id)
        .order_by(LeadAssignmentHistory.assigned_at.desc())
        .all()
    )
    return jsonify({'assignment_history': [h.to_dict() for h in history]}), 200


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

@leads_bp.route('/<int:lead_id>/notes', methods=['GET'])
@require_auth
def get_lead_notes(lead_id):
    if not Lead.query.get(lead_id):
        return jsonify({'error': 'Lead not found'}), 404
    notes = (
        LeadNote.query
        .filter_by(lead_id=lead_id)
        .order_by(LeadNote.created_at.desc())
        .all()
    )
    return jsonify({'notes': [n.to_dict() for n in notes]}), 200


@leads_bp.route('/<int:lead_id>/notes', methods=['POST'])
@require_auth
def add_lead_note(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    data = request.get_json() or {}
    note_text = data.get('note', '').strip()
    if not note_text:
        return jsonify({'error': 'Note text is required'}), 400

    note = LeadNote(lead_id=lead_id, note=note_text, created_by=user.id)
    db.session.add(note)
    db.session.commit()

    log_activity(
        user.id, 'add_note', 'leads', lead_id, 'LeadNote',
        description=f'Added note to lead {lead.name}',
    )
    return jsonify({'note': note.to_dict()}), 201


# ---------------------------------------------------------------------------
# Dashboard stats (placed here as they are lead-centric)
# ---------------------------------------------------------------------------

@leads_bp.route('/dashboard/stats', methods=['GET'])
@require_auth
def dashboard_stats():
    user = request.current_user
    statuses = VALID_STATUSES

    def apply_time_filter(query):
        range_key = (request.args.get('range') or '').strip().lower()
        date_from_str = request.args.get('date_from')
        date_to_str = request.args.get('date_to')
        now = datetime.now()

        if date_from_str or date_to_str:
            try:
                if date_from_str:
                    dt_from = datetime.strptime(date_from_str, '%Y-%m-%d')
                    query = query.filter(Lead.created_at >= dt_from)
                if date_to_str:
                    dt_to = datetime.strptime(date_to_str, '%Y-%m-%d') + timedelta(days=1)
                    query = query.filter(Lead.created_at < dt_to)
                return query
            except ValueError:
                return query

        if range_key == 'today':
            start = datetime(now.year, now.month, now.day)
            return query.filter(Lead.created_at >= start)
        if range_key == 'this_week':
            start = datetime(now.year, now.month, now.day) - timedelta(days=now.weekday())
            return query.filter(Lead.created_at >= start)
        if range_key == 'this_month':
            start = datetime(now.year, now.month, 1)
            return query.filter(Lead.created_at >= start)
        if range_key == 'last_30_days':
            start = now - timedelta(days=30)
            return query.filter(Lead.created_at >= start)
        return query

    def apply_project_filter(query):
        project_id = request.args.get('project_id')
        if project_id:
            try:
                return query.filter(Lead.project_id == int(project_id))
            except ValueError:
                return query
        return query

    def calc_rates(total, counts):
        if total == 0:
            return {'hot_rate': 0, 'warm_rate': 0}
        warm = (counts.get('follow_up', 0) + counts.get('callback_scheduled', 0) + counts.get('interested', 0))
        site_visit = counts.get('site_visit_planned', 0) + counts.get('site_visit_done', 0)
        hot = site_visit + counts.get('negotiation', 0) + counts.get('booking_done', 0)
        return {
            'hot_rate': round(hot / total * 100, 1),
            'warm_rate': round(warm / total * 100, 1),
        }

    tid_scope = request.current_tenant_id
    team_ids = None

    if user.role == 'sales_manager':
        team_ids = [r[0] for r in User.query.filter_by(manager_id=user.id).with_entities(User.id).all()]

    def scoped_query_for_role():
        if user.role in ('superadmin', 'platform_owner'):
            q = Lead.query.filter_by(is_active=True, tenant_id=tid_scope)
        elif user.role == 'sales_manager':
            q = Lead.query.filter(
                Lead.is_active == True,
                Lead.tenant_id == tid_scope,
                db.or_(
                    Lead.sales_manager_id == user.id,
                    Lead.assigned_to == user.id,
                    Lead.assigned_to.in_(team_ids or [-1]),
                )
            )
        else:
            q = Lead.query.filter_by(assigned_to=user.id, is_active=True, tenant_id=tid_scope)
        return apply_project_filter(apply_time_filter(q))

    base_q = scoped_query_for_role()
    lead_scope = base_q.with_entities(
        Lead.id.label('id'),
        Lead.status.label('status'),
        Lead.source.label('source'),
        Lead.project_id.label('project_id'),
        Lead.assigned_to.label('assigned_to'),
    ).subquery()

    status_count_exprs = [
        func.coalesce(func.sum(case((lead_scope.c.status == s, 1), else_=0)), 0).label(f'{s}_count')
        for s in statuses
    ]
    overall_row = db.session.query(
        func.count(lead_scope.c.id).label('total'),
        func.coalesce(func.sum(case((lead_scope.c.assigned_to.isnot(None), 1), else_=0)), 0).label('assigned'),
        func.coalesce(func.sum(case((lead_scope.c.assigned_to.is_(None), 1), else_=0)), 0).label('unassigned'),
        *status_count_exprs,
    ).select_from(lead_scope).one()

    status_counts = {s: int(getattr(overall_row, f'{s}_count') or 0) for s in statuses}
    status_counts['assigned'] = int(overall_row.assigned or 0)
    status_counts['unassigned'] = int(overall_row.unassigned or 0)
    total = int(overall_row.total or 0)
    rates = calc_rates(total, status_counts)

    source_rows = (
        db.session.query(
            lead_scope.c.source.label('source'),
            func.count(lead_scope.c.id).label('count'),
        )
        .select_from(lead_scope)
        .group_by(lead_scope.c.source)
        .order_by(func.count(lead_scope.c.id).desc())
        .all()
    )
    source_total = sum(int(r.count or 0) for r in source_rows)
    source_stats = []
    for row in source_rows:
        count = int(row.count or 0)
        if count == 0:
            continue
        source_stats.append({
            'source': row.source or 'Unknown',
            'count': count,
            'percent': round((count / source_total * 100), 1) if source_total else 0,
        })

    project_count_exprs = [
        func.coalesce(func.sum(case((lead_scope.c.status == s, 1), else_=0)), 0).label(f'{s}_count')
        for s in statuses
    ]
    project_rows = (
        db.session.query(
            Project.id.label('project_id'),
            Project.name.label('project_name'),
            func.count(lead_scope.c.id).label('total'),
            *project_count_exprs,
        )
        .select_from(Project)
        .outerjoin(lead_scope, lead_scope.c.project_id == Project.id)
        .filter(Project.is_active == True, Project.tenant_id == tid_scope)
        .group_by(Project.id, Project.name)
        .order_by(Project.name)
        .all()
    )

    def _project_row_to_dict(row):
        counts = {s: int(getattr(row, f'{s}_count') or 0) for s in statuses}
        total_count = int(row.total or 0)
        project_rates = calc_rates(total_count, counts)
        return {
            'project_id': row.project_id,
            'project_name': row.project_name,
            'total': total_count,
            'status_counts': counts,
            'hot_rate': project_rates['hot_rate'],
            'warm_rate': project_rates['warm_rate'],
        }

    project_stats = [_project_row_to_dict(row) for row in project_rows]

    if user.role in ('superadmin', 'platform_owner'):
        stats = {
            'total_leads': total,
            'total_team_members': db.session.query(func.count(User.id)).filter(
                User.role == 'team_member',
                User.tenant_id == tid_scope,
                User.is_active == True,
            ).scalar(),
            'total_projects': len(project_rows),
            'status_counts': status_counts,
            'hot_rate': rates['hot_rate'],
            'warm_rate': rates['warm_rate'],
            'source_stats': source_stats,
            'project_stats': project_stats,
        }
    elif user.role == 'sales_manager':
        stats = {
            'my_leads': total,
            'team_size': len(team_ids or []),
            'total_projects': len(project_rows),
            'status_counts': status_counts,
            'hot_rate': rates['hot_rate'],
            'warm_rate': rates['warm_rate'],
            'source_stats': source_stats,
            'project_stats': project_stats,
        }
    else:
        stats = {
            'my_leads': total,
            'status_counts': status_counts,
            'hot_rate': rates['hot_rate'],
            'warm_rate': rates['warm_rate'],
            'source_stats': source_stats,
            'project_stats': project_stats,
        }

    return jsonify({'stats': stats}), 200


# ---------------------------------------------------------------------------
# Daily Action Board
# ---------------------------------------------------------------------------

@leads_bp.route('/action-board', methods=['GET'])
@require_auth
def action_board():
    """Return all data needed for the Daily Action Board for the current user."""
    user = request.current_user
    page_size = 20
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_end   = today_start + timedelta(days=1)

    date_from_str = (request.args.get('date_from') or '').strip()
    date_to_str = (request.args.get('date_to') or '').strip()
    range_requested = bool(date_from_str or date_to_str)

    range_start = today_start
    range_end = today_end
    if range_requested:
        try:
            if date_from_str:
                range_start = datetime.strptime(date_from_str, '%Y-%m-%d')
            elif date_to_str:
                range_start = datetime.strptime(date_to_str, '%Y-%m-%d')

            if date_to_str:
                range_end = datetime.strptime(date_to_str, '%Y-%m-%d') + timedelta(days=1)
            else:
                range_end = range_start + timedelta(days=1)
        except ValueError:
            range_requested = False
            range_start = today_start
            range_end = today_end

    visible = get_user_visible_leads(user)

    if range_requested:
        lead_scope = visible.filter(
            db.or_(
                db.and_(Lead.created_at >= range_start, Lead.created_at < range_end),
                db.and_(Lead.updated_at >= range_start, Lead.updated_at < range_end),
            )
        )
    else:
        lead_scope = visible

    visible_ids = [r[0] for r in visible.with_entities(Lead.id).all()]

    # ── Callback queries (scoped by role) ────────────────────────────────────
    cb_base = CallbackReminder.query.filter(
        CallbackReminder.tenant_id == user.tenant_id,
        CallbackReminder.status == 'pending',
    )
    if user.role == 'team_member':
        cb_base = cb_base.filter(CallbackReminder.assigned_user_id == user.id)
    elif user.role == 'sales_manager':
        team_ids = [u.id for u in User.query.filter_by(manager_id=user.id).all()]
        team_ids.append(user.id)
        cb_base = cb_base.filter(
            db.or_(
                CallbackReminder.assigned_user_id.in_(team_ids),
                CallbackReminder.manager_id == user.id,
            )
        )

    # Keep callbacks in the same visibility boundary as lead lists.
    if visible_ids:
        cb_base = cb_base.filter(CallbackReminder.lead_id.in_(visible_ids))
    else:
        cb_base = cb_base.filter(db.text('1=0'))

    callback_window_start = range_start if range_requested else today_start
    callback_window_end   = range_end if range_requested else today_end

    current_callbacks = cb_base.filter(
        CallbackReminder.callback_datetime >= callback_window_start,
        CallbackReminder.callback_datetime <  callback_window_end,
    ).order_by(CallbackReminder.callback_datetime.asc()).all()

    overdue_callbacks = cb_base.filter(
        CallbackReminder.callback_datetime < callback_window_start,
    ).order_by(CallbackReminder.callback_datetime.asc()).all()

    def _page_param(name):
        try:
            return max(1, int(request.args.get(name, 1)))
        except (TypeError, ValueError):
            return 1

    section_pages = {
        'today_callbacks': _page_param('today_callbacks_page'),
        'overdue_callbacks': _page_param('overdue_callbacks_page'),
        'new_leads_today': _page_param('new_leads_today_page'),
        'follow_up': _page_param('follow_up_page'),
        'no_answer': _page_param('no_answer_page'),
        'warm_leads': _page_param('warm_leads_page'),
        'hot_leads': _page_param('hot_leads_page'),
    }

    def _slice_page(items, page):
        start = (page - 1) * page_size
        end = start + page_size
        return items[start:end]

    def _query_page(query, page, sort_col, desc=False):
        ordered = query.order_by(sort_col.desc() if desc else sort_col.asc())
        start = (page - 1) * page_size
        return ordered.offset(start).limit(page_size).all()

    def _pagination_meta(total, page, shown):
        start = ((page - 1) * page_size) + 1 if shown else 0
        end = start + shown - 1 if shown else 0
        return {
            'page': page,
            'page_size': page_size,
            'total': total,
            'shown': shown,
            'start': start,
            'end': end,
            'has_prev': page > 1,
            'has_next': end < total,
        }

    def _cb_dict(c):
        d = c.to_dict()
        lead = c.lead
        d['lead_name'] = lead.name if lead else f'Lead #{c.lead_id}'
        d['lead_phone'] = lead.phone if lead else None
        d['lead_status'] = lead.status if lead else None
        d['project_name'] = lead.project.name if lead and lead.project else None
        d['project_id'] = lead.project_id if lead else None
        if lead and lead.notes:
            latest_note = sorted(lead.notes, key=lambda n: n.created_at or datetime.min, reverse=True)[0]
            d['latest_note'] = latest_note.note if latest_note else None
        else:
            d['latest_note'] = None
        return d

    # ── Lead section buckets (per Action Board spec) ─────────────────────────
    # 2.3 New Leads Today: status=new + created today/range + newly assigned in range
    # 2.4 Follow Up: follow_up + callback_scheduled where callback is from previous days
    # 2.5 No Answer: all no_answer (today + past)
    # 2.6 Warm: interested + site_visit_planned
    # 2.7 Hot:  site_visit_done + negotiation
    warm_statuses = ['interested', 'site_visit_planned']
    hot_statuses = ['site_visit_done', 'negotiation']

    # assignment-based expansion for "new assigned for today/range"
    assigned_ids = []
    if visible_ids:
        assign_q = LeadAssignmentHistory.query.filter(
            LeadAssignmentHistory.lead_id.in_(visible_ids),
            LeadAssignmentHistory.assigned_at >= callback_window_start,
            LeadAssignmentHistory.assigned_at < callback_window_end,
            LeadAssignmentHistory.assigned_to.isnot(None),
        )
        if user.role == 'team_member':
            assign_q = assign_q.filter(LeadAssignmentHistory.assigned_to == user.id)
        elif user.role == 'sales_manager':
            team_ids = [u.id for u in User.query.filter_by(manager_id=user.id).all()]
            team_ids.append(user.id)
            assign_q = assign_q.filter(LeadAssignmentHistory.assigned_to.in_(team_ids))
        assigned_ids = [r[0] for r in assign_q.with_entities(LeadAssignmentHistory.lead_id).distinct().all()]

    overdue_callback_lead_ids = list({c.lead_id for c in overdue_callbacks if c.lead_id})

    new_clauses = [
        Lead.status == 'new',
        db.and_(Lead.created_at >= callback_window_start, Lead.created_at < callback_window_end),
    ]
    if assigned_ids:
        new_clauses.append(Lead.id.in_(assigned_ids))
    new_bucket_q = visible.filter(db.or_(*new_clauses))

    follow_clauses = [Lead.status == 'follow_up']
    if overdue_callback_lead_ids:
        follow_clauses.append(
            db.and_(Lead.status == 'callback_scheduled', Lead.id.in_(overdue_callback_lead_ids))
        )
    follow_up_q = visible.filter(db.or_(*follow_clauses))
    no_answer_q = visible.filter(Lead.status == 'no_answer')
    warm_q = visible.filter(Lead.status.in_(warm_statuses))
    hot_q = visible.filter(Lead.status.in_(hot_statuses))

    # counts
    today_callbacks_count = len(current_callbacks)
    overdue_callbacks_count = len(overdue_callbacks)
    new_today_count = new_bucket_q.count()
    follow_up_count = follow_up_q.count()
    no_answer_count = no_answer_q.count()
    warm_count = warm_q.count()
    hot_count = hot_q.count()

    # paged section lists
    current_callbacks_page = _slice_page(current_callbacks, section_pages['today_callbacks'])
    overdue_callbacks_page = _slice_page(overdue_callbacks, section_pages['overdue_callbacks'])
    new_today = _query_page(new_bucket_q, section_pages['new_leads_today'], Lead.created_at, desc=True)
    follow_up = _query_page(follow_up_q, section_pages['follow_up'], Lead.updated_at, desc=False)
    no_answer = _query_page(no_answer_q, section_pages['no_answer'], Lead.updated_at, desc=False)
    warm_leads = _query_page(warm_q, section_pages['warm_leads'], Lead.updated_at, desc=True)
    hot_leads = _query_page(hot_q, section_pages['hot_leads'], Lead.updated_at, desc=True)

    return jsonify({
        'today_callbacks':   [_cb_dict(c) for c in current_callbacks_page],
        'overdue_callbacks':  [_cb_dict(c) for c in overdue_callbacks_page],
        'new_leads_today':   [l.to_dict() for l in new_today],
        'follow_up_leads':   [l.to_dict() for l in follow_up],
        'no_answer_leads':   [l.to_dict() for l in no_answer],
        'warm_leads':        [l.to_dict() for l in warm_leads],
        'hot_leads':         [l.to_dict() for l in hot_leads],
        'summary': {
            'today_callbacks_count': today_callbacks_count,
            'overdue_count':         overdue_callbacks_count,
            'new_leads_count':       new_today_count,
            'follow_up_count':       follow_up_count,
            'no_answer_count':       no_answer_count,
            'warm_leads_count':      warm_count,
            'hot_leads_count':       hot_count,
        },
        'pagination': {
            'today_callbacks': _pagination_meta(today_callbacks_count, section_pages['today_callbacks'], len(current_callbacks_page)),
            'overdue_callbacks': _pagination_meta(overdue_callbacks_count, section_pages['overdue_callbacks'], len(overdue_callbacks_page)),
            'new_leads_today': _pagination_meta(new_today_count, section_pages['new_leads_today'], len(new_today)),
            'follow_up': _pagination_meta(follow_up_count, section_pages['follow_up'], len(follow_up)),
            'no_answer': _pagination_meta(no_answer_count, section_pages['no_answer'], len(no_answer)),
            'warm_leads': _pagination_meta(warm_count, section_pages['warm_leads'], len(warm_leads)),
            'hot_leads': _pagination_meta(hot_count, section_pages['hot_leads'], len(hot_leads)),
        },
        'selected_range': {
            'date_from': range_start.date().isoformat(),
            'date_to': (range_end - timedelta(days=1)).date().isoformat(),
            'range_requested': range_requested,
        },
    }), 200


# ---------------------------------------------------------------------------
# Lead Recycle Queue
# ---------------------------------------------------------------------------

RECYCLE_STATUSES = ['no_answer', 'not_interested', 'follow_up', 'callback_scheduled', 'lost']


@leads_bp.route('/recycle-queue', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def recycle_queue():
    """Return leads eligible for recycling/reshuffling."""
    user = request.current_user
    stale_mode = (request.args.get('stale_mode') or '').strip().lower()
    stale_days = max(1, int(request.args.get('stale_days', 3)))
    date_from_str = (request.args.get('date_from') or '').strip()
    date_to_str = (request.args.get('date_to') or '').strip()
    status_filter = request.args.get('status')   # optional single-status filter
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    tomorrow_start = today_start + timedelta(days=1)
    yesterday_start = today_start - timedelta(days=1)

    base = get_user_visible_leads(user)
    statuses = [status_filter] if status_filter and status_filter in RECYCLE_STATUSES else RECYCLE_STATUSES

    if stale_mode == 'today':
        base = base.filter(
            Lead.status.in_(statuses),
            Lead.updated_at >= today_start,
            Lead.updated_at < tomorrow_start,
        )
    elif stale_mode == 'yesterday':
        base = base.filter(
            Lead.status.in_(statuses),
            Lead.updated_at >= yesterday_start,
            Lead.updated_at < today_start,
        )
    elif stale_mode == 'custom':
        range_start = None
        range_end = None
        try:
            if date_from_str:
                range_start = datetime.strptime(date_from_str, '%Y-%m-%d')
            if date_to_str:
                range_end = datetime.strptime(date_to_str, '%Y-%m-%d') + timedelta(days=1)
        except ValueError:
            range_start = None
            range_end = None

        base = base.filter(Lead.status.in_(statuses))
        if range_start:
            base = base.filter(Lead.updated_at >= range_start)
        if range_end:
            base = base.filter(Lead.updated_at < range_end)
    else:
        stale_before = now - timedelta(days=stale_days)
        base = base.filter(Lead.status.in_(statuses), Lead.updated_at <= stale_before)

    total = base.count()
    leads = base.order_by(Lead.updated_at.asc()).limit(100).all()

    # For each lead, attach previous assignees (for display in the UI)
    def _with_history(lead):
        d = lead.to_dict()
        prev = (
            LeadAssignmentHistory.query
            .filter(LeadAssignmentHistory.lead_id == lead.id,
                    LeadAssignmentHistory.assigned_to.isnot(None))
            .with_entities(LeadAssignmentHistory.assigned_to)
            .all()
        )
        d['previous_assignee_ids'] = list({r[0] for r in prev if r[0]})
        return d

    return jsonify({
        'leads':      [_with_history(l) for l in leads],
        'total':      total,
        'stale_days': stale_days,
        'stale_mode': stale_mode or 'older_than_days',
        'selected_range': {
            'date_from': date_from_str or None,
            'date_to': date_to_str or None,
        },
    }), 200


# ---------------------------------------------------------------------------
# Lead Auto-Reshuffle
# ---------------------------------------------------------------------------

@leads_bp.route('/reshuffle', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def reshuffle_leads():
    """
    Intelligent cooldown-based lead reshuffle.

    Strategy options:
      intelligent (default) — Cooldown-Based Intelligent Recycling:
        1. Unattempted users first (never had this lead)
        2. Least-recently-assigned users outside cooldown window
        3. Fallback: least-recently-assigned ignoring cooldown (round-robin)
        Never assigns back to current assignee consecutively.
      round_robin  — simple balanced rotation (no cooldown).
      least_loaded — assign to team member with fewest active leads.

    Body: { lead_ids, strategy, reason, cooldown_days }
    """
    user         = request.current_user
    data         = request.get_json() or {}
    lead_ids     = data.get('lead_ids', [])
    strategy     = data.get('strategy', 'intelligent')
    reason       = (data.get('reason') or 'Reshuffle').strip()
    cooldown_days = max(1, int(data.get('cooldown_days', 7)))

    if not lead_ids:
        return jsonify({'error': 'lead_ids is required'}), 400
    if len(lead_ids) > 200:
        return jsonify({'error': 'Max 200 leads per reshuffle'}), 400

    # Gather eligible team members
    if user.role == 'sales_manager':
        team = User.query.filter_by(manager_id=user.id, is_active=True).all()
    else:  # superadmin
        team = User.query.filter_by(role='team_member', tenant_id=user.tenant_id, is_active=True).all()

    if not team:
        return jsonify({'error': 'No active team members available'}), 400

    # Pre-compute active lead counts for all team members (used by multiple strategies)
    NON_ACTIVE = ['lost', 'junk', 'booking_done', 'not_interested']
    load_counts: dict = {}
    for tm in team:
        load_counts[tm.id] = Lead.query.filter(
            Lead.assigned_to == tm.id,
            Lead.is_active == True,
            Lead.status.notin_(NON_ACTIVE),
        ).count()

    cooldown_threshold = datetime.utcnow() - timedelta(days=cooldown_days)

    def _get_next_assignee_intelligent(lead):
        """Cooldown-Based Intelligent Recycling algorithm."""
        current_uid = lead.assigned_to

        # Full assignment history for this lead (most recent per user)
        history = LeadAssignmentHistory.query.filter_by(lead_id=lead.id).all()
        last_assigned: dict = {}  # user_id -> most recent assigned_at
        for h in history:
            if h.assigned_to:
                if h.assigned_to not in last_assigned or h.assigned_at > last_assigned[h.assigned_to]:
                    last_assigned[h.assigned_to] = h.assigned_at

        # Candidates: exclude current user (Rule 1 — no consecutive same user)
        candidates = [u for u in team if u.id != current_uid]
        if not candidates:
            # Only one team member — must assign back but log it
            return team[0]

        def _load(u):
            return load_counts.get(u.id, 0)

        # TIER 1 — Users who have NEVER received this lead (highest priority)
        tier1 = [u for u in candidates if u.id not in last_assigned]
        if tier1:
            tier1.sort(key=_load)  # balanced distribution
            return tier1[0]

        # TIER 2 — Users whose last assignment was outside the cooldown window
        tier2 = [u for u in candidates
                 if last_assigned.get(u.id, datetime.min) < cooldown_threshold]
        if tier2:
            # Sort: least recently assigned first, then by workload
            tier2.sort(key=lambda u: (last_assigned[u.id], _load(u)))
            return tier2[0]

        # TIER 3 — Fallback: all candidates, least recently assigned
        # (cooldown override — all in cooldown but assignment must proceed)
        candidates.sort(key=lambda u: (last_assigned.get(u.id, datetime.min), _load(u)))
        return candidates[0]

    rr_index  = 0
    reshuffled = 0
    assignments = []

    for lead_id in lead_ids:
        lead = Lead.query.filter_by(id=lead_id, tenant_id=user.tenant_id, is_active=True).first()
        if not lead:
            continue

        # Manager scope check
        if user.role == 'sales_manager':
            team_ids = {tm.id for tm in team} | {user.id}
            if lead.assigned_to not in team_ids and lead.sales_manager_id != user.id:
                continue

        # Skip permanently closed leads
        if lead.status in ['lost', 'junk']:
            continue

        # Select new assignee per strategy
        if strategy == 'intelligent':
            new_assignee = _get_next_assignee_intelligent(lead)
        elif strategy == 'least_loaded':
            prev_ids = {
                h.assigned_to
                for h in LeadAssignmentHistory.query.filter_by(lead_id=lead_id).all()
                if h.assigned_to
            }
            prev_ids.add(lead.assigned_to)
            cands = [u for u in team if u.id not in prev_ids] or team
            new_assignee = min(cands, key=lambda u: load_counts.get(u.id, 0))
            load_counts[new_assignee.id] = load_counts.get(new_assignee.id, 0) + 1
        else:  # round_robin
            prev_ids = {
                h.assigned_to
                for h in LeadAssignmentHistory.query.filter_by(lead_id=lead_id).all()
                if h.assigned_to
            }
            prev_ids.add(lead.assigned_to)
            cands = [u for u in team if u.id not in prev_ids] or team
            new_assignee = cands[rr_index % len(cands)]
            rr_index += 1

        old_assignee_id = lead.assigned_to
        db.session.add(LeadAssignmentHistory(
            lead_id=lead_id,
            assigned_from=old_assignee_id,
            assigned_to=new_assignee.id,
            assigned_by=user.id,
            reason=reason,
        ))
        lead.assigned_to = new_assignee.id
        lead.assigned_by = user.id
        # Increment load counter so subsequent leads in same batch account for this
        load_counts[new_assignee.id] = load_counts.get(new_assignee.id, 0) + 1

        log_activity(
            user.id, 'reshuffle_lead', 'leads', lead_id, 'Lead',
            description=f'Reshuffled lead {lead.name} to {new_assignee.name} (strategy={strategy})',
        )

        old_name = (User.query.get(old_assignee_id).name
                    if old_assignee_id else 'Unassigned')
        assignments.append({
            'lead_id':        lead_id,
            'lead_name':      lead.name,
            'from_user_id':   old_assignee_id,
            'from_user_name': old_name,
            'to_user_id':     new_assignee.id,
            'to_user_name':   new_assignee.name,
        })
        reshuffled += 1

    db.session.commit()
    return jsonify({'reshuffled': reshuffled, 'assignments': assignments}), 200


# ---------------------------------------------------------------------------
# Callback Reminders
# ---------------------------------------------------------------------------

def _check_lead_access(user, lead):
    """Return 403 response if user cannot access the lead, else None."""
    if not lead or lead.tenant_id != user.tenant_id:
        return jsonify({'error': 'Lead not found'}), 404
    if user.role == 'team_member' and lead.assigned_to != user.id:
        return jsonify({'error': 'Access denied'}), 403
    if user.role == 'sales_manager':
        team_ids = {u.id for u in User.query.filter_by(manager_id=user.id).all()}
        team_ids.add(user.id)
        if lead.assigned_to not in team_ids and lead.sales_manager_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
    return None


@leads_bp.route('/<int:lead_id>/call-activity', methods=['POST'])
@require_auth
def log_call_activity(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    err = _check_lead_access(user, lead)
    if err:
        return err

    data = request.get_json() or {}
    event_type = (data.get('event_type') or 'outcome').strip().lower()
    outcome = (data.get('outcome') or '').strip().lower()
    note = (data.get('note') or '').strip()
    source = (data.get('source') or '').strip()

    if event_type not in ('initiated', 'outcome'):
        return jsonify({'error': 'event_type must be initiated or outcome'}), 400
    if event_type == 'outcome' and outcome not in CALL_OUTCOME_LABELS:
        return jsonify({'error': 'Valid outcome is required'}), 400

    action = 'call_initiated' if event_type == 'initiated' else f'call_{outcome}'
    description = (
        f'Initiated call for lead {lead.name}'
        if event_type == 'initiated'
        else f'Call outcome for lead {lead.name}: {CALL_OUTCOME_LABELS[outcome]}'
    )
    if note:
        description = description + (f' — {note}' if event_type == 'outcome' else f' ({note})')

    log_activity(
        user.id,
        action,
        'leads',
        lead_id,
        'LeadCall',
        new_value={
            'event_type': event_type,
            'outcome': outcome or None,
            'outcome_label': CALL_OUTCOME_LABELS.get(outcome),
            'note': note or None,
            'source': source or None,
            'phone': lead.phone,
        },
        description=description,
    )
    return jsonify({'ok': True}), 200


@leads_bp.route('/<int:lead_id>/activity-timeline', methods=['GET'])
@require_auth
def get_call_activity_timeline(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    err = _check_lead_access(user, lead)
    if err:
        return err

    call_logs = (
        ActivityLog.query
        .filter(
            ActivityLog.resource_id == lead_id,
            ActivityLog.module == 'leads',
            ActivityLog.action.like('call_%'),
        )
        .order_by(ActivityLog.created_at.asc())
        .all()
    )
    return jsonify({'call_activities': [log.to_dict() for log in call_logs]}), 200


@leads_bp.route('/<int:lead_id>/callbacks', methods=['GET'])
@require_auth
def get_callbacks(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    err = _check_lead_access(user, lead)
    if err:
        return err
    cbs = CallbackReminder.query.filter_by(lead_id=lead_id).order_by(
        CallbackReminder.callback_datetime.asc()
    ).all()
    return jsonify({'callbacks': [c.to_dict() for c in cbs]}), 200


@leads_bp.route('/<int:lead_id>/callbacks', methods=['POST'])
@require_auth
def create_callback(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    err = _check_lead_access(user, lead)
    if err:
        return err

    data = request.get_json() or {}
    raw_dt = data.get('callback_datetime', '').strip()
    if not raw_dt:
        return jsonify({'error': 'callback_datetime is required'}), 400

    try:
        cb_dt = datetime.fromisoformat(raw_dt.replace('Z', '+00:00').split('+')[0])
    except ValueError:
        return jsonify({'error': 'Invalid datetime format. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS)'}), 400

    if cb_dt <= datetime.utcnow():
        return jsonify({'error': 'Callback time must be in the future'}), 400

    # Determine manager_id: from lead's sales_manager, or assigned user's manager
    manager_id = lead.sales_manager_id
    if not manager_id and lead.assigned_to:
        assigned = User.query.get(lead.assigned_to)
        if assigned:
            manager_id = assigned.manager_id

    cb = CallbackReminder(
        lead_id=lead_id,
        tenant_id=user.tenant_id,
        assigned_user_id=lead.assigned_to,
        manager_id=manager_id,
        callback_datetime=cb_dt,
        notes=data.get('notes', '').strip() or None,
        created_by=user.id,
    )
    db.session.add(cb)
    db.session.commit()

    log_activity(
        user.id, 'create_callback', 'leads', lead_id, 'Lead',
        description=f'Scheduled callback for lead {lead.name} at {cb_dt.strftime("%Y-%m-%d %H:%M")}',
    )
    return jsonify({'callback': cb.to_dict()}), 201


@leads_bp.route('/callbacks/<int:callback_id>/complete', methods=['POST'])
@require_auth
def complete_callback(callback_id):
    user = request.current_user
    cb = CallbackReminder.query.get(callback_id)
    if not cb or cb.tenant_id != user.tenant_id:
        return jsonify({'error': 'Callback not found'}), 404
    cb.status = 'completed'
    db.session.commit()
    log_activity(
        user.id, 'complete_callback', 'leads', cb.lead_id, 'Lead',
        description=f'Marked callback as completed',
    )
    return jsonify({'callback': cb.to_dict()}), 200


@leads_bp.route('/callbacks/<int:callback_id>', methods=['DELETE'])
@require_auth
def delete_callback(callback_id):
    user = request.current_user
    cb = CallbackReminder.query.get(callback_id)
    if not cb or cb.tenant_id != user.tenant_id:
        return jsonify({'error': 'Callback not found'}), 404
    # Only the creator, assigned user, or admin/manager may delete
    if user.role == 'team_member' and cb.assigned_user_id != user.id:
        return jsonify({'error': 'Access denied'}), 403
    db.session.delete(cb)
    db.session.commit()
    return jsonify({'message': 'Callback deleted'}), 200


@leads_bp.route('/callbacks/upcoming', methods=['GET'])
@require_auth
def upcoming_callbacks():
    """Returns callbacks due in the next 24 hours for the current user."""
    user = request.current_user
    now = datetime.utcnow()
    window = now + timedelta(hours=24)

    query = CallbackReminder.query.filter(
        CallbackReminder.tenant_id == user.tenant_id,
        CallbackReminder.status == 'pending',
        CallbackReminder.callback_datetime >= now,
        CallbackReminder.callback_datetime <= window,
    )
    if user.role == 'team_member':
        query = query.filter(CallbackReminder.assigned_user_id == user.id)
    elif user.role == 'sales_manager':
        team_ids = [u.id for u in User.query.filter_by(manager_id=user.id).all()]
        team_ids.append(user.id)
        query = query.filter(
            db.or_(
                CallbackReminder.assigned_user_id.in_(team_ids),
                CallbackReminder.manager_id == user.id,
            )
        )
    # superadmin: all tenant callbacks

    cbs = query.order_by(CallbackReminder.callback_datetime.asc()).all()
    return jsonify({'callbacks': [c.to_dict() for c in cbs]}), 200
