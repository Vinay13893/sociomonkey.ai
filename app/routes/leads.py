from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta

from app.middleware import require_auth, require_role
from app.models.base import db
from app.models.lead import Lead, StatusHistory, LeadNote, LeadAssignmentHistory, CallbackReminder
from app.models.project import Project
from app.models.user import User
from app.utils.activity import log_activity
from app.utils.leads import get_user_visible_leads, VALID_STATUSES

leads_bp = Blueprint('leads', __name__, url_prefix='/api/leads')


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
        """Calculate hot_rate and warm_rate."""
        if total == 0:
            return {'hot_rate': 0, 'warm_rate': 0}
        warm = (counts.get('follow_up', 0) + counts.get('callback_scheduled', 0)
                + counts.get('interested', 0))
        site_visit = counts.get('site_visit_planned', 0) + counts.get('site_visit_done', 0)
        hot = site_visit + counts.get('negotiation', 0) + counts.get('booking_done', 0)
        return {
            'hot_rate': round(hot / total * 100, 1),
            'warm_rate': round(warm / total * 100, 1),
        }

    def source_stats_for(base_query):
        rows = (
            base_query
            .with_entities(Lead.source, db.func.count(Lead.id))
            .group_by(Lead.source)
            .all()
        )
        total = sum(r[1] for r in rows)
        out = []
        for source, count in rows:
            if count == 0:
                continue
            out.append({
                'source': source or 'Unknown',
                'count': count,
                'percent': round((count / total * 100), 1) if total else 0,
            })
        out.sort(key=lambda x: x['count'], reverse=True)
        return out

    def project_stats_for(base_query):
        """Return per-project status counts for the given base query."""
        # Use the request-scoped tenant_id so platform_owner drilling into a
        # tenant sees that tenant's projects (not the platform's empty set).
        tid_scope = request.current_tenant_id
        projects = Project.query.filter_by(is_active=True, tenant_id=tid_scope).order_by(Project.name).all()
        result = []
        for p in projects:
            q = base_query.filter(Lead.project_id == p.id)
            counts = {s: q.filter(Lead.status == s).count() for s in statuses}
            total = q.count()
            rates = calc_rates(total, counts)
            result.append({
                'project_id':   p.id,
                'project_name': p.name,
                'total':        total,
                'status_counts': counts,
                'hot_rate': rates['hot_rate'],
                'warm_rate': rates['warm_rate'],
            })
        return result

    def scoped_query_for_role():
        # request.current_tenant_id is the authoritative tenant scope.
        # For normal tenant users it equals user.tenant_id; for platform_owner
        # drilling into a tenant via X-Tenant-Slug it is the target tenant's id.
        tid = request.current_tenant_id
        if user.role in ('superadmin', 'platform_owner'):
            q = Lead.query.filter_by(is_active=True, tenant_id=tid)
        elif user.role == 'sales_manager':
            team_ids = [tm.id for tm in user.team_members]
            q = Lead.query.filter(
                Lead.is_active == True,
                Lead.tenant_id == tid,
                db.or_(
                    Lead.sales_manager_id == user.id,
                    Lead.assigned_to == user.id,
                    Lead.assigned_to.in_(team_ids),
                )
            )
        else:
            q = Lead.query.filter_by(assigned_to=user.id, is_active=True, tenant_id=tid)
        q = apply_time_filter(q)
        q = apply_project_filter(q)
        return q

    if user.role in ('superadmin', 'platform_owner'):
        base_q = scoped_query_for_role()
        status_counts = {s: base_q.filter_by(status=s).count() for s in statuses}
        status_counts['assigned']   = base_q.filter(Lead.assigned_to.isnot(None)).count()
        status_counts['unassigned'] = base_q.filter(Lead.assigned_to.is_(None)).count()
        total = base_q.count()
        rates = calc_rates(total, status_counts)
        # Use request.current_tenant_id for tenant-scoped counts so platform_owner
        # viewing a tenant via X-Tenant-Slug gets that tenant's data.
        tid_scope = request.current_tenant_id
        stats = {
            'total_leads': total,
            'total_team_members': User.query.filter_by(role='team_member', tenant_id=tid_scope).count(),
            'total_projects': Project.query.filter_by(is_active=True, tenant_id=tid_scope).count(),
            'status_counts': status_counts,
            'hot_rate': rates['hot_rate'],
            'warm_rate': rates['warm_rate'],
            'source_stats': source_stats_for(base_q),
            'project_stats': project_stats_for(scoped_query_for_role()),
        }
    elif user.role == 'sales_manager':
        base_q = scoped_query_for_role()
        status_counts = {
            s: base_q.filter(Lead.status == s).count()
            for s in statuses
        }
        status_counts['assigned']   = base_q.filter(Lead.assigned_to.isnot(None)).count()
        status_counts['unassigned'] = base_q.filter(Lead.assigned_to.is_(None)).count()
        total = base_q.count()
        rates = calc_rates(total, status_counts)
        stats = {
            'my_leads': total,
            'team_size': len(user.team_members),
            'total_projects': Project.query.filter_by(is_active=True, tenant_id=user.tenant_id).count(),
            'status_counts': status_counts,
            'hot_rate': rates['hot_rate'],
            'warm_rate': rates['warm_rate'],
            'source_stats': source_stats_for(base_q),
            'project_stats': project_stats_for(scoped_query_for_role()),
        }
    else:
        base_q = scoped_query_for_role()
        status_counts = {
            s: base_q.filter_by(status=s).count()
            for s in statuses
        }
        status_counts['assigned']   = base_q.count()
        status_counts['unassigned'] = 0
        total = base_q.count()
        rates = calc_rates(total, status_counts)
        stats = {
            'my_leads': total,
            'status_counts': status_counts,
            'hot_rate': rates['hot_rate'],
            'warm_rate': rates['warm_rate'],
            'source_stats': source_stats_for(base_q),
            'project_stats': project_stats_for(scoped_query_for_role()),
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
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_end   = today_start + timedelta(days=1)

    visible = get_user_visible_leads(user)

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

    today_callbacks   = cb_base.filter(
        CallbackReminder.callback_datetime >= today_start,
        CallbackReminder.callback_datetime <  today_end,
    ).order_by(CallbackReminder.callback_datetime.asc()).all()

    overdue_callbacks = cb_base.filter(
        CallbackReminder.callback_datetime < today_start,
    ).order_by(CallbackReminder.callback_datetime.asc()).all()

    def _cb_dict(c):
        d = c.to_dict()
        d['lead_name']   = c.lead.name   if c.lead else f'Lead #{c.lead_id}'
        d['lead_phone']  = c.lead.phone  if c.lead else None
        d['lead_status'] = c.lead.status if c.lead else None
        return d

    # ── Lead section counts (for summary, separate from limited lists) ────────
    hot_statuses = ['interested', 'site_visit_planned', 'site_visit_done', 'negotiation']
    new_today_count      = visible.filter(Lead.created_at >= today_start, Lead.created_at < today_end).count()
    follow_up_count      = visible.filter(Lead.status.in_(['follow_up', 'callback_scheduled'])).count()
    no_answer_count      = visible.filter(Lead.status == 'no_answer').count()
    hot_count            = visible.filter(Lead.status.in_(hot_statuses)).count()

    # ── Lead lists (limited to 20 per section) ────────────────────────────────
    new_today   = visible.filter(Lead.created_at >= today_start, Lead.created_at < today_end
                                ).order_by(Lead.created_at.desc()).limit(20).all()
    follow_up   = visible.filter(Lead.status.in_(['follow_up', 'callback_scheduled'])
                                ).order_by(Lead.updated_at.asc()).limit(20).all()
    no_answer   = visible.filter(Lead.status == 'no_answer'
                                ).order_by(Lead.updated_at.asc()).limit(20).all()
    hot_leads   = visible.filter(Lead.status.in_(hot_statuses)
                                ).order_by(Lead.updated_at.desc()).limit(20).all()

    return jsonify({
        'today_callbacks':   [_cb_dict(c) for c in today_callbacks],
        'overdue_callbacks':  [_cb_dict(c) for c in overdue_callbacks],
        'new_leads_today':   [l.to_dict() for l in new_today],
        'follow_up_leads':   [l.to_dict() for l in follow_up],
        'no_answer_leads':   [l.to_dict() for l in no_answer],
        'hot_leads':         [l.to_dict() for l in hot_leads],
        'summary': {
            'today_callbacks_count': len(today_callbacks),
            'overdue_count':         len(overdue_callbacks),
            'new_leads_count':       new_today_count,
            'follow_up_count':       follow_up_count,
            'no_answer_count':       no_answer_count,
            'hot_leads_count':       hot_count,
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
    stale_days = max(1, int(request.args.get('stale_days', 3)))
    status_filter = request.args.get('status')   # optional single-status filter
    stale_before  = datetime.utcnow() - timedelta(days=stale_days)

    base = get_user_visible_leads(user)
    statuses = [status_filter] if status_filter and status_filter in RECYCLE_STATUSES else RECYCLE_STATUSES
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
