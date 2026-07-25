from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta, timezone
import random

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import selectinload, joinedload

from app.middleware import require_auth, require_role
from app.models.base import db
from app.models.activity import ActivityLog
from app.models.lead import Lead, StatusHistory, LeadNote, LeadAssignmentHistory, CallbackReminder
from app.models.ingestion import IngestedLeadLog
from app.models.job import LeadReshuffleJob
from app.models.project import Project
from app.models.user import User
from app.models.ingestion import LeadSource
from app.utils.activity import log_activity
from app.utils.correlation import request_correlation_id
from app.utils.leads import (
    get_user_visible_leads,
    apply_test_lead_filter,
    apply_valid_lead_capture_scope,
    VALID_STATUSES,
)
from app.utils.time_utils import (
    business_date_bounds_utc_naive,
    IST,
    parse_business_datetime_to_utc_naive,
    now_ist,
    to_ist_str,
)
from app.services.callback_workflow import (
    CALLBACK_PENDING_ERROR,
    cancel_callback_record,
    complete_callback_record,
    create_callback_for_lead,
    reschedule_callback,
)
from app.services.reminder_scheduler import push_notification

leads_bp = Blueprint('leads', __name__, url_prefix='/api/leads')

CALL_OUTCOME_LABELS = {
    'connected': 'Connected',
    'no_answer': 'No Answer',
    'busy': 'Busy',
    'wrong_number': 'Wrong Number',
    'callback_scheduled': 'Callback Scheduled',
}

def _parse_ist_datetime(raw_value):
    return parse_business_datetime_to_utc_naive(raw_value)


def _format_ist_datetime(value):
    if not value:
        return ''
    dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).strftime('%d %b %Y %H:%M IST')


def _runtime_prefers_async_jobs() -> bool:
    import os
    return (os.environ.get('VERCEL') or '').strip().lower() in {'1', 'true', 'yes'}


def _process_reshuffle_job(job, user, team, strategy, reason, cooldown_days):
    # Pre-compute active lead counts for all team members (used by multiple strategies)
    load_counts: dict = {}
    for tm in team:
        load_counts[tm.id] = Lead.query.filter(
            Lead.assigned_to == tm.id,
            Lead.is_active == True,
            Lead.status.notin_(TERMINAL_LEAD_STATUSES),
        ).count()

    cooldown_threshold = datetime.utcnow() - timedelta(days=cooldown_days)

    def _get_next_assignee_intelligent(lead):
        current_uid = lead.assigned_to

        history = LeadAssignmentHistory.query.filter_by(lead_id=lead.id).all()
        last_assigned: dict = {}
        for h in history:
            if h.assigned_to:
                if h.assigned_to not in last_assigned or h.assigned_at > last_assigned[h.assigned_to]:
                    last_assigned[h.assigned_to] = h.assigned_at

        candidates = [u for u in team if u.id != current_uid]
        if not candidates:
            return team[0]

        def _load(u):
            return load_counts.get(u.id, 0)

        tier1 = [u for u in candidates if u.id not in last_assigned]
        if tier1:
            tier1.sort(key=_load)
            return tier1[0]

        tier2 = [u for u in candidates if last_assigned.get(u.id, datetime.min) < cooldown_threshold]
        if tier2:
            tier2.sort(key=lambda u: (last_assigned[u.id], _load(u)))
            return tier2[0]

        candidates.sort(key=lambda u: (last_assigned.get(u.id, datetime.min), _load(u)))
        return candidates[0]

    rr_index = 0
    reshuffled = 0
    assignments = []

    for lead_id in job.lead_ids:
        lead = Lead.query.filter_by(id=lead_id, tenant_id=user.tenant_id, is_active=True).first()
        if not lead:
            continue

        if user.role == 'sales_manager':
            team_ids = {tm.id for tm in team} | {user.id}
            if lead.assigned_to not in team_ids and lead.sales_manager_id != user.id:
                continue

        if lead.status in TERMINAL_LEAD_STATUSES:
            continue

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
        else:
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
            tenant_id=lead.tenant_id,
            lead_id=lead_id,
            assigned_from=old_assignee_id,
            assigned_to=new_assignee.id,
            assigned_by=user.id,
            reason=reason,
            source='RESHUFFLE',
            correlation_id=request.headers.get('X-Correlation-ID'),
        ))
        lead.assigned_to = new_assignee.id
        lead.assigned_by = user.id
        CallbackReminder.query.filter(
            CallbackReminder.tenant_id == user.tenant_id,
            CallbackReminder.lead_id == lead.id,
            CallbackReminder.status == 'pending',
        ).update({'assigned_user_id': new_assignee.id}, synchronize_session=False)
        load_counts[new_assignee.id] = load_counts.get(new_assignee.id, 0) + 1

        log_activity(
            user.id, 'reshuffle_lead', 'leads', lead_id, 'Lead',
            description=f'Reshuffled lead {lead.name} to {new_assignee.name} (strategy={strategy})',
        )

        old_name = (User.query.get(old_assignee_id).name if old_assignee_id else 'Unassigned')
        assignments.append({
            'lead_id': lead_id,
            'lead_name': lead.name,
            'from_user_id': old_assignee_id,
            'from_user_name': old_name,
            'to_user_id': new_assignee.id,
            'to_user_name': new_assignee.name,
        })
        reshuffled += 1

    job.status = 'completed'
    job.completed_at = datetime.utcnow()
    job.summary = {'reshuffled': reshuffled, 'assignments': assignments}
    db.session.commit()
    return {'job': job.to_dict(), 'reshuffled': reshuffled, 'assignments': assignments}


def process_queued_reshuffle_jobs(limit: int = 10) -> dict:
    processed = failed = 0
    rows = (
        LeadReshuffleJob.query
        .filter(LeadReshuffleJob.status.in_(['queued', 'processing']))
        .order_by(LeadReshuffleJob.created_at.asc())
        .limit(max(1, int(limit)))
        .all()
    )
    for job in rows:
        if job.status == 'completed':
            continue
        user = job.user
        if not user:
            job.status = 'failed'
            job.error_message = 'Job owner not found'
            job.completed_at = datetime.utcnow()
            db.session.commit()
            failed += 1
            continue

        if user.role == 'sales_manager':
            team = User.query.filter_by(manager_id=user.id, is_active=True).all()
        else:
            team = User.query.filter_by(role='team_member', tenant_id=user.tenant_id, is_active=True).all()

        if not team:
            job.status = 'failed'
            job.error_message = 'No active team members available'
            job.completed_at = datetime.utcnow()
            db.session.commit()
            failed += 1
            continue

        try:
            job.status = 'processing'
            job.started_at = job.started_at or datetime.utcnow()
            db.session.commit()
            _process_reshuffle_job(job, user, team, job.strategy, job.reason, job.cooldown_days)
            processed += 1
        except Exception as exc:
            db.session.rollback()
            job.status = 'failed'
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            db.session.commit()
            failed += 1

    return {'queued_scanned': len(rows), 'processed': processed, 'failed': failed}


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

LEADS_DEFAULT_PAGE_SIZE = 50
LEADS_MAX_PAGE_SIZE = 100
LEADS_MAX_IDS_REFRESH = 100


def _parse_positive_int(raw_value, default, minimum=1, maximum=None):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _parse_leads_datetime(raw_value):
    if not raw_value:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw_value).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _parse_lead_ids(raw_value):
    ids = []
    seen = set()
    for part in str(raw_value or '').split(','):
        try:
            lead_id = int(part.strip())
        except (TypeError, ValueError):
            continue
        if lead_id > 0 and lead_id not in seen:
            seen.add(lead_id)
            ids.append(lead_id)
        if len(ids) >= LEADS_MAX_IDS_REFRESH:
            break
    return ids


def _apply_lead_source_cutoff_scope(query, user, tenant_id):
    return apply_valid_lead_capture_scope(query, tenant_id)


@leads_bp.route('', methods=['GET'])
@require_auth
def get_leads():
    user = request.current_user
    query = get_user_visible_leads(user)

    page = _parse_positive_int(request.args.get('page'), 1)
    page_size = _parse_positive_int(
        request.args.get('page_size') or request.args.get('per_page'),
        LEADS_DEFAULT_PAGE_SIZE,
        maximum=LEADS_MAX_PAGE_SIZE,
    )
    if str(request.args.get('page_size') or request.args.get('per_page') or '').strip() == '0':
        page_size = LEADS_MAX_PAGE_SIZE
    project_id = request.args.get('project_id')
    status = (request.args.get('status') or '').strip()
    source = (request.args.get('source') or '').strip()
    assigned_to = (request.args.get('assigned_to') or request.args.get('team_member') or '').strip()
    sales_manager_id = (request.args.get('sales_manager_id') or '').strip()
    date_from = (request.args.get('date_from') or '').strip()
    date_to = (request.args.get('date_to') or '').strip()
    search = (request.args.get('q') or request.args.get('search') or '').strip()
    sort = (request.args.get('sort') or 'new_old').strip()
    updated_since = _parse_leads_datetime(request.args.get('updated_since'))
    requested_ids = _parse_lead_ids(request.args.get('ids'))
    query = _apply_lead_source_cutoff_scope(query, user, user.tenant_id)
    if project_id:
        try:
            query = query.filter(Lead.project_id == int(project_id))
        except ValueError:
            return jsonify({'error': 'project_id must be an integer'}), 400
    if status:
        query = query.filter(Lead.status == status)
    if source:
        query = query.filter(Lead.source == source)
    if assigned_to == 'unassigned':
        query = query.filter(Lead.assigned_to.is_(None))
    elif assigned_to:
        try:
            query = query.filter(Lead.assigned_to == int(assigned_to))
        except ValueError:
            return jsonify({'error': 'assigned_to must be an integer or unassigned'}), 400
    if sales_manager_id:
        try:
            query = query.filter(Lead.sales_manager_id == int(sales_manager_id))
        except ValueError:
            return jsonify({'error': 'sales_manager_id must be an integer'}), 400
    if date_from:
        try:
            start, _ = business_date_bounds_utc_naive(datetime.strptime(date_from, '%Y-%m-%d').date())
            query = query.filter(Lead.created_at >= start)
        except ValueError:
            return jsonify({'error': 'date_from must be YYYY-MM-DD'}), 400
    if date_to:
        try:
            _, end = business_date_bounds_utc_naive(datetime.strptime(date_to, '%Y-%m-%d').date())
            query = query.filter(Lead.created_at < end)
        except ValueError:
            return jsonify({'error': 'date_to must be YYYY-MM-DD'}), 400
    if search:
        like_q = f'%{search.lower()}%'
        query = query.outerjoin(Project, Lead.project_id == Project.id).filter(or_(
            func.lower(func.coalesce(Lead.name, '')).like(like_q),
            func.lower(func.coalesce(Lead.phone, '')).like(like_q),
            func.lower(func.coalesce(Lead.email, '')).like(like_q),
            func.lower(func.coalesce(Project.name, '')).like(like_q),
        ))
    if requested_ids:
        query = query.filter(Lead.id.in_(requested_ids))
    if updated_since:
        query = query.filter(or_(Lead.updated_at > updated_since, Lead.created_at > updated_since))

    # Eager-load all relationships used by to_dict() to avoid N+1 queries.
    # Without this, each lead triggers separate SELECT for notes, callbacks,
    # and assigned_user.manager — causing thousands of DB round-trips.
    query = query.options(
        joinedload(Lead.project),
        joinedload(Lead.assigned_user).joinedload(User.manager),
        joinedload(Lead.sales_manager),
    )

    total = int(query.enable_eagerloads(False).order_by(None).with_entities(func.count(Lead.id)).scalar() or 0)
    sort_map = {
        'old_new': (Lead.created_at.asc(), Lead.id.asc()),
        'updated_new_old': (Lead.updated_at.desc(), Lead.id.desc()),
        'updated_old_new': (Lead.updated_at.asc(), Lead.id.asc()),
        'new_old': (Lead.created_at.desc(), Lead.id.desc()),
    }
    order_by = sort_map.get(sort, sort_map['new_old'])
    if sort not in sort_map:
        sort = 'new_old'
    if requested_ids:
        page = 1
        page_size = min(max(len(requested_ids), 1), LEADS_MAX_IDS_REFRESH)
    if updated_since and not requested_ids:
        page = 1
        page_size = min(page_size, LEADS_MAX_PAGE_SIZE)
        order_by = sort_map['updated_new_old']
        sort = 'updated_new_old'

    leads = list(
        query
        .order_by(*order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    lead_ids = [lead.id for lead in leads]
    latest_notes = {}
    next_callbacks = {}

    if lead_ids:
        latest_note_subq = (
            db.session.query(
                LeadNote.lead_id.label('lead_id'),
                func.max(LeadNote.created_at).label('latest_created_at'),
            )
            .filter(LeadNote.lead_id.in_(lead_ids))
            .group_by(LeadNote.lead_id)
            .subquery()
        )
        latest_note_rows = (
            db.session.query(LeadNote.lead_id, LeadNote.note)
            .join(
                latest_note_subq,
                and_(
                    LeadNote.lead_id == latest_note_subq.c.lead_id,
                    LeadNote.created_at == latest_note_subq.c.latest_created_at,
                ),
            )
            .all()
        )
        latest_notes = {
            row.lead_id: (row.note or '')[:120]
            for row in latest_note_rows
        }

        next_callback_rows = (
            db.session.query(
                CallbackReminder.lead_id.label('lead_id'),
                func.min(CallbackReminder.callback_datetime).label('next_callback'),
            )
            .filter(
                CallbackReminder.lead_id.in_(lead_ids),
                CallbackReminder.status == 'pending',
                CallbackReminder.callback_datetime > datetime.utcnow(),
            )
            .group_by(CallbackReminder.lead_id)
            .all()
        )
        next_callbacks = {
            row.lead_id: to_ist_str(row.next_callback)
            for row in next_callback_rows
        }

    def lead_list_dict(lead):
        return {
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'alternate_phone': lead.alternate_phone,
            'email': lead.email,
            'source': lead.source,
            'budget_min': lead.budget_min,
            'budget_max': lead.budget_max,
            'project_id': lead.project_id,
            'project_name': lead.project.name if lead.project else None,
            'status': lead.status,
            'assigned_to': lead.assigned_to,
            'assigned_to_name': lead.assigned_user.name if lead.assigned_user else None,
            'sales_manager_id': lead.sales_manager_id,
            'sales_manager_name': lead.sales_manager.name if lead.sales_manager else None,
            'manager_name': (
                lead.assigned_user.manager.name
                if lead.assigned_user and lead.assigned_user.manager
                else None
            ),
            'created_at': to_ist_str(lead.created_at),
            'updated_at': to_ist_str(lead.updated_at),
            'is_test': lead.is_test,
            'latest_note': latest_notes.get(lead.id),
            'next_callback': next_callbacks.get(lead.id),
        }

    total_pages = max(1, (total + page_size - 1) // page_size)
    server_time = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
    return jsonify({
        'leads': [lead_list_dict(lead) for lead in leads],
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
            'max_page_size': LEADS_MAX_PAGE_SIZE,
        },
        'sort': sort,
        'mode': 'ids' if requested_ids else ('delta' if updated_since else 'page'),
        'server_time': server_time,
    }), 200


@leads_bp.route('', methods=['POST'])
@require_role('superadmin', 'sales_manager', 'team_member')
def create_lead():
    user = request.current_user
    data = request.get_json() or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'error': 'Lead name is required'}), 400

    phone_val = (data.get('phone') or '').strip()
    alternate_phone_val = (data.get('alternate_phone') or '').strip()
    email_val = (data.get('email') or '').strip()
    if not any((phone_val, alternate_phone_val, email_val)):
        return jsonify({'error': 'At least one contact method is required'}), 400
    if phone_val:
        force = data.get('force') and user.role == 'superadmin'
        if not force:
            existing = Lead.query.filter(
                Lead.phone == phone_val,
                Lead.tenant_id == user.tenant_id,
                Lead.is_active == True,
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
        phone=phone_val or None,
        alternate_phone=alternate_phone_val or None,
        email=email_val or None,
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

    # Notify assigned team member about new lead (if assigned and not the creator)
    if lead.assigned_to and lead.assigned_to != user.id:
        push_notification(lead.assigned_to, {
            'type': 'lead_assigned',
            'kind': 'info',
            'title': 'New Lead Assigned',
            'message': f'📋 New lead "{lead.name}" has been assigned to you.',
            'lead_id': lead.id,
            'lead_name': lead.name,
            'source': 'lead_created',
            'tenant_id': lead.tenant_id,
        })
        try:
            from app.services.notification_events import enqueue_lead_assigned
            assigned_user = User.query.get(lead.assigned_to)
            if assigned_user:
                enqueue_lead_assigned(assigned_user, lead)
                db.session.commit()
        except Exception:
            db.session.rollback()

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
    if user.role == 'superadmin':
        lead.phone = (data.get('phone') or lead.phone or '').strip() or None
    lead.alternate_phone = (data.get('alternate_phone') or lead.alternate_phone or '').strip() or None
    lead.email = data.get('email', lead.email)
    lead.source = data.get('source', lead.source)
    lead.budget_min = data.get('budget_min', lead.budget_min)
    lead.budget_max = data.get('budget_max', lead.budget_max)
    lead.project_id = data.get('project_id', lead.project_id)

    new_status = data.get('status')
    if new_status and new_status != old_status:
        from app.services.pipeline_engine import (
            PipelineTransitionError, transition_lead,
        )
        try:
            transition_lead(
                lead, new_status, actor=user, source='LEAD_EDIT',
                reason=data.get('status_reason'),
                context=data.get('pipeline_context')
                if isinstance(data.get('pipeline_context'), dict) else {},
                correlation_id=request.headers.get('X-Correlation-ID'),
            )
        except PipelineTransitionError as exc:
            db.session.rollback()
            return jsonify({
                'error': str(exc), 'code': exc.code, 'details': exc.details,
            }), 409 if exc.code == 'RULES_NOT_SATISFIED' else 400

    changes = []
    if old_data.get('phone') != lead.phone:
        changes.append(f"primary number {old_data.get('phone') or '—'} → {lead.phone or '—'}")
    if old_data.get('alternate_phone') != lead.alternate_phone:
        changes.append(f"alternate number {old_data.get('alternate_phone') or '—'} → {lead.alternate_phone or '—'}")
    if old_data.get('project_id') != lead.project_id:
        old_project = old_data.get('project_name') or old_data.get('project_id') or '—'
        new_project = lead.project.name if lead.project else (lead.project_id or '—')
        changes.append(f"project {old_project} → {new_project}")
    if old_data.get('source') != lead.source:
        changes.append(f"source {old_data.get('source') or '—'} → {lead.source or '—'}")
    if old_data.get('name') != lead.name:
        changes.append(f"name {old_data.get('name') or '—'} → {lead.name or '—'}")
    if old_data.get('email') != lead.email:
        changes.append(f"email {old_data.get('email') or '—'} → {lead.email or '—'}")
    budget_old = f"{old_data.get('budget_min') or '—'}–{old_data.get('budget_max') or '—'}"
    budget_new = f"{lead.budget_min or '—'}–{lead.budget_max or '—'}"
    if budget_old != budget_new:
        changes.append(f"budget {budget_old} → {budget_new}")

    db.session.commit()

    for change in changes:
        log_activity(
            user.id,
            'update_lead',
            'leads',
            lead_id,
            'Lead',
            description=f'Updated lead {lead.name} ({change})',
        )

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
        from app.services.pipeline_engine import (
            PipelineTransitionError, transition_lead,
        )
        try:
            transition_lead(
                lead, new_status, actor=user, source='LEAD_BULK_STATUS',
                reason=data.get('reason'),
                correlation_id=request.headers.get('X-Correlation-ID'),
            )
        except PipelineTransitionError as exc:
            db.session.rollback()
            return jsonify({
                'error': str(exc), 'code': exc.code, 'details': exc.details,
                'lead_id': lead_id,
            }), 409 if exc.code == 'RULES_NOT_SATISFIED' else 400
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

    base_sources = ['Website','Referral','Walk-in','Meta','Google',
                    'Email Campaign','Direct','Other','G1','G2','G3','TP']
    source_names = [
        name for name, in db.session.query(LeadSource.name)
        .filter(LeadSource.tenant_id == user.tenant_id, LeadSource.is_active == True)
        .all()
        if name
    ]
    valid_sources = []
    seen_sources = set()
    for source_name in base_sources + source_names:
        key = str(source_name or '').strip().lower()
        if key and key not in seen_sources:
            seen_sources.add(key)
            valid_sources.append(str(source_name).strip())
    if not lead_ids:
        return jsonify({'error': 'lead_ids is required'}), 400
    if not new_source or new_source not in valid_sources:
        return jsonify({'error': f'Invalid source. Must be one of: {", ".join(valid_sources)}'}), 400

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
    operation_correlation = request_correlation_id(request)
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
                    tenant_id=lead.tenant_id,
                    lead_id=lead_id,
                    assigned_from=lead.assigned_to,
                    assigned_to=assigned_to,
                    assigned_by=user.id,
                    source='LEADS_BULK_ASSIGN',
                    correlation_id=operation_correlation,
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
        tenant_id=user.tenant_id,
        correlation_id=operation_correlation,
    )

    # Notify the assignee (member bulk-assign only, skip manager-column assignments and self-assign)
    if assign_type == 'member' and assigned_to is not None and assigned_to != user.id and updated > 0:
        target = User.query.get(assigned_to)
        if target:
            push_notification(assigned_to, {
                'type': 'lead_assigned',
                'kind': 'info',
                'title': 'New Leads Assigned',
                'message': f'📋 {updated} lead{"s" if updated != 1 else ""} {"have" if updated != 1 else "has"} been assigned to you by {user.name}.',
                'source': 'bulk_assignment',
                'tenant_id': target.tenant_id,
                'correlation_id': operation_correlation,
            })
            try:
                from app.services.notification_events import enqueue_lead_assigned
                # Enqueue one event summarising the bulk assignment (first lead as anchor)
                first_lead_id = lead_ids[0] if lead_ids else None
                first_lead = Lead.query.get(first_lead_id) if first_lead_id else None
                if first_lead:
                    ev = enqueue_lead_assigned(
                        target, first_lead,
                        correlation_id=operation_correlation,
                        idempotency_key=(
                            f'bulk-assignment:{operation_correlation}:'
                            f'user:{target.id}'
                        ),
                    )
                    # Override title/body for bulk context
                    ev.title = 'New Leads Assigned'
                    ev.body = f'{updated} new lead{"s" if updated != 1 else ""} assigned to you'
                    db.session.commit()
            except Exception:
                db.session.rollback()

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
    operation_correlation = request_correlation_id(request)
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
        tenant_id=lead.tenant_id,
        lead_id=lead_id,
        assigned_from=lead.assigned_to,
        assigned_to=assigned_to,
        assigned_by=user.id,
        reason=data.get('reason'),
        source='LEADS_ASSIGN',
        correlation_id=operation_correlation,
    )
    old_name = User.query.get(lead.assigned_to).name if lead.assigned_to else 'Unassigned'
    lead.assigned_to = assigned_to
    lead.assigned_by = user.id
    db.session.add(assignment)
    db.session.commit()

    log_activity(
        user.id, 'assign_lead', 'leads', lead_id, 'Lead',
        description=f'Assigned lead {lead.name} from {old_name} to {target.name}',
        tenant_id=lead.tenant_id,
        correlation_id=operation_correlation,
    )

    # Notify the newly assigned team member (skip if assigning to self)
    if target.id != user.id:
        push_notification(target.id, {
            'type': 'lead_assigned',
            'kind': 'info',
            'title': 'New Lead Assigned',
            'message': f'📋 Lead "{lead.name}" has been assigned to you by {user.name}.',
            'lead_id': lead_id,
            'lead_name': lead.name,
            'source': 'lead_assignment',
            'tenant_id': lead.tenant_id,
            'correlation_id': operation_correlation,
        })
        try:
            from app.services.notification_events import enqueue_lead_reassigned
            enqueue_lead_reassigned(
                target, lead,
                correlation_id=operation_correlation,
                idempotency_key=(
                    f'lead-reassignment:{lead.id}:{operation_correlation}:'
                    f'user:{target.id}'
                ),
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

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
        now_local = now_ist()

        if date_from_str or date_to_str:
            try:
                if date_from_str:
                    dt_from, _ = business_date_bounds_utc_naive(datetime.strptime(date_from_str, '%Y-%m-%d').date())
                    query = query.filter(Lead.created_at >= dt_from)
                if date_to_str:
                    _, dt_to = business_date_bounds_utc_naive(datetime.strptime(date_to_str, '%Y-%m-%d').date())
                    query = query.filter(Lead.created_at < dt_to)
                return query
            except ValueError:
                return query

        if range_key == 'today':
            start, end = business_date_bounds_utc_naive(now_local.date())
            return query.filter(Lead.created_at >= start, Lead.created_at < end)
        if range_key == 'this_week':
            start_day = now_local.date() - timedelta(days=now_local.weekday())
            start, _ = business_date_bounds_utc_naive(start_day)
            return query.filter(Lead.created_at >= start)
        if range_key == 'this_month':
            start, _ = business_date_bounds_utc_naive(now_local.date().replace(day=1))
            return query.filter(Lead.created_at >= start)
        if range_key == 'last_30_days':
            start = (now_local - timedelta(days=30)).astimezone(timezone.utc).replace(tzinfo=None)
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

    def apply_dashboard_filters(query):
        source = (request.args.get('source') or '').strip()
        status = (request.args.get('status') or '').strip()
        assigned_to = (request.args.get('assigned_to') or '').strip()
        if source:
            query = query.filter(Lead.source == source)
        if status:
            query = query.filter(Lead.status == status)
        if assigned_to == 'unassigned':
            query = query.filter(Lead.assigned_to.is_(None))
        elif assigned_to:
            try:
                query = query.filter(Lead.assigned_to == int(assigned_to))
            except ValueError:
                pass
        return query

    def calc_rates(total, counts):
        if total == 0:
            return {'hot_rate': 0, 'warm_rate': 0}
        warm = counts.get('interested', 0) + counts.get('site_visit_planned', 0)
        hot = counts.get('site_visit_done', 0) + counts.get('negotiation', 0)
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
        q = apply_test_lead_filter(q)
        q = _apply_lead_source_cutoff_scope(q, user, tid_scope)
        return apply_dashboard_filters(apply_project_filter(apply_time_filter(q)))

    scoped_query = scoped_query_for_role()

    total = int(scoped_query.order_by(None).with_entities(func.count(Lead.id)).scalar() or 0)

    status_rows = (
        scoped_query
        .order_by(None)
        .with_entities(Lead.status.label('status'), func.count(Lead.id).label('count'))
        .group_by(Lead.status)
        .all()
    )
    status_counter = {row.status: int(row.count or 0) for row in status_rows if row.status}
    status_counts = {s: int(status_counter.get(s, 0)) for s in statuses}

    assigned_total = int(
        scoped_query
        .order_by(None)
        .filter(Lead.assigned_to.isnot(None))
        .with_entities(func.count(Lead.id))
        .scalar() or 0
    )
    status_counts['assigned'] = assigned_total
    status_counts['unassigned'] = total - status_counts['assigned']
    rates = calc_rates(total, status_counts)

    source_rows = (
        scoped_query
        .order_by(None)
        .with_entities(func.coalesce(Lead.source, 'Unknown').label('source'), func.count(Lead.id).label('count'))
        .group_by(func.coalesce(Lead.source, 'Unknown'))
        .order_by(func.count(Lead.id).desc())
        .all()
    )
    source_total = sum(int(row.count or 0) for row in source_rows)
    source_stats = []
    for row in source_rows:
        source_name = row.source or 'Unknown'
        source_count = row.count
        count = int(source_count or 0)
        if count == 0:
            continue
        source_stats.append({
            'source': source_name,
            'count': count,
            'percent': round((count / source_total * 100), 1) if source_total else 0,
        })

    project_rows = (
        Project.query
        .with_entities(Project.id.label('project_id'), Project.name.label('project_name'))
        .filter(Project.is_active == True, Project.tenant_id == tid_scope)
        .order_by(Project.name)
        .all()
    )
    project_buckets = {
        row.project_id: {
            'project_id': row.project_id,
            'project_name': row.project_name,
            'total': 0,
            'status_counts': {s: 0 for s in statuses},
        }
        for row in project_rows
    }

    project_status_rows = (
        scoped_query
        .order_by(None)
        .with_entities(
            Lead.project_id.label('project_id'),
            Lead.status.label('status'),
            func.count(Lead.id).label('count'),
        )
        .group_by(Lead.project_id, Lead.status)
        .all()
    )
    for row in project_status_rows:
        bucket = project_buckets.get(row.project_id)
        if not bucket:
            continue
        count = int(row.count or 0)
        bucket['total'] += count
        if row.status in bucket['status_counts']:
            bucket['status_counts'][row.status] += count

    project_stats = []
    for row in project_rows:
        project_data = project_buckets[row.project_id]
        project_rates = calc_rates(project_data['total'], project_data['status_counts'])
        project_stats.append({
            'project_id': project_data['project_id'],
            'project_name': project_data['project_name'],
            'total': project_data['total'],
            'status_counts': project_data['status_counts'],
            'hot_rate': project_rates['hot_rate'],
            'warm_rate': project_rates['warm_rate'],
        })

    if user.role in ('superadmin', 'platform_owner'):
        stats = {
            'total_leads': total,
            'total_team_members': db.session.query(func.count(User.id)).filter(
                User.role == 'team_member',
                User.tenant_id == tid_scope,
                User.is_active == True,
            ).scalar(),
            'total_projects': len(project_stats),
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
            'total_projects': len(project_stats),
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

    # ── view_as: manager/admin can view another user's board ─────────────────
    view_as_id = request.args.get('view_as', type=int)
    viewing_user = user  # default: own board
    if view_as_id and view_as_id != user.id:
        if user.role not in ('superadmin', 'sales_manager'):
            return jsonify({'error': 'Permission denied'}), 403
        target = User.query.filter_by(id=view_as_id, tenant_id=user.tenant_id).first()
        if not target:
            return jsonify({'error': 'User not found'}), 404
        if user.role == 'sales_manager':
            # Manager can only view their own direct reports
            team_ids = [tm.id for tm in user.team_members]
            if target.id not in team_ids:
                return jsonify({'error': 'Permission denied'}), 403
        viewing_user = target
    try:
        page_size = max(5, min(24, int(request.args.get('page_size', 6))))
    except (TypeError, ValueError):
        page_size = 6
    today_ist = now_ist().date()
    today_start, today_end = business_date_bounds_utc_naive(today_ist)

    date_from_str = (request.args.get('date_from') or '').strip()
    date_to_str = (request.args.get('date_to') or '').strip()
    range_requested = bool(date_from_str or date_to_str)

    range_start = today_start
    range_end = today_end
    selected_from_date = today_ist
    selected_to_date = today_ist
    if range_requested:
        try:
            if date_from_str:
                from_date = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            elif date_to_str:
                from_date = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            else:
                from_date = today_ist

            if date_to_str:
                to_date = datetime.strptime(date_to_str, '%Y-%m-%d').date()
            else:
                to_date = from_date
            range_start, _ = business_date_bounds_utc_naive(from_date)
            _, range_end = business_date_bounds_utc_naive(to_date)
            selected_from_date = from_date
            selected_to_date = to_date
        except ValueError:
            range_requested = False
            range_start = today_start
            range_end = today_end
            selected_from_date = today_ist
            selected_to_date = today_ist

    visible = get_user_visible_leads(viewing_user)
    board_visible = visible.filter(Lead.assigned_to == viewing_user.id)

    if range_requested:
        lead_scope = board_visible.filter(
            db.or_(
                db.and_(Lead.created_at >= range_start, Lead.created_at < range_end),
                db.and_(Lead.updated_at >= range_start, Lead.updated_at < range_end),
            )
        )
    else:
        lead_scope = board_visible

    visible_ids_subq = board_visible.with_entities(Lead.id.label('id')).subquery()

    # ── Callback queries (scoped by role) ────────────────────────────────────
    cb_base = CallbackReminder.query.filter(
        CallbackReminder.tenant_id == viewing_user.tenant_id,
        CallbackReminder.status == 'pending',
        CallbackReminder.assigned_user_id == viewing_user.id,
    )

    # Keep callbacks in the same visibility boundary as lead lists.
    # Use a subquery instead of materializing lead IDs in Python to avoid
    # large IN lists and expensive memory usage on tenants with many leads.
    cb_base = cb_base.filter(
        CallbackReminder.lead_id.in_(db.select(visible_ids_subq.c.id))
    )

    callback_window_start = range_start if range_requested else today_start
    callback_window_end   = range_end if range_requested else today_end

    ranked_callbacks = (
        cb_base
        .with_entities(
            CallbackReminder.id.label('id'),
            CallbackReminder.lead_id.label('lead_id'),
            func.row_number().over(
                partition_by=CallbackReminder.lead_id,
                order_by=(CallbackReminder.callback_datetime.asc(), CallbackReminder.id.asc()),
            ).label('rn'),
        )
        .subquery()
    )
    first_callback_ids = (
        db.session.query(ranked_callbacks.c.id)
        .filter(ranked_callbacks.c.rn == 1)
        .subquery()
    )
    first_callback_lead_ids = (
        db.session.query(ranked_callbacks.c.lead_id)
        .filter(ranked_callbacks.c.rn == 1, ranked_callbacks.c.lead_id.isnot(None))
        .subquery()
    )
    unique_cb_base = (
        CallbackReminder.query
        .filter(CallbackReminder.id.in_(db.select(first_callback_ids.c.id)))
        .options(
            joinedload(CallbackReminder.lead).joinedload(Lead.project),
            joinedload(CallbackReminder.lead).joinedload(Lead.assigned_user),
        )
    )

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

    def _query_page(query, page, *order_by):
        ordered = query.order_by(*order_by)
        start = (page - 1) * page_size
        return list(ordered.offset(start).limit(page_size))

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
        lead = c.lead
        latest_note = latest_notes.get(c.lead_id) if c.lead_id else None
        return {
            'id': c.id,
            'lead_id': c.lead_id,
            'callback_datetime': to_ist_str(c.callback_datetime),
            'status': c.status,
            'notes': c.notes,
            'lead_name': lead.name if lead else f'Lead #{c.lead_id}',
            'lead_phone': lead.phone if lead else None,
            'lead_alternate_phone': lead.alternate_phone if lead else None,
            'lead_email': lead.email if lead else None,
            'lead_source': lead.source if lead else None,
            'lead_status': lead.status if lead else None,
            'lead_created_at': to_ist_str(lead.created_at) if lead and lead.created_at else None,
            'lead_untouched_days': max(0, (datetime.utcnow() - lead.updated_at).days) if lead and lead.updated_at else 0,
            'project_name': lead.project.name if lead and lead.project else None,
            'project_id': lead.project_id if lead else None,
            'assigned_to_name': lead.assigned_user.name if lead and lead.assigned_user else None,
            'latest_note': latest_note,
        }

    def _lead_card_dict(lead):
        return {
            'id': lead.id,
            'name': lead.name,
            'phone': lead.phone,
            'alternate_phone': lead.alternate_phone,
            'email': lead.email,
            'source': lead.source,
            'project_id': lead.project_id,
            'project_name': lead.project.name if lead.project else None,
            'status': lead.status,
            'assigned_to': lead.assigned_to,
            'assigned_to_name': lead.assigned_user.name if lead.assigned_user else None,
            'sales_manager_id': lead.sales_manager_id,
            'sales_manager_name': lead.sales_manager.name if lead.sales_manager else None,
            'created_at': to_ist_str(lead.created_at),
            'updated_at': to_ist_str(lead.updated_at),
            'days_untouched': max(0, (datetime.utcnow() - lead.updated_at).days) if lead.updated_at else 0,
            'latest_note': latest_notes.get(lead.id),
            'next_callback': None,
        }

    # ── Lead section buckets (per Action Board spec) ─────────────────────────
    # Callback-first precedence: any lead with a pending callback reminder
    # is represented in callback sections and excluded from status buckets.
    # 2.3 New Leads Today: status=new + created today/range + assigned_to current user
    # 2.4 Follow Up: follow_up (excluding callback-covered leads)
    # 2.5 No Answer: all no_answer (excluding callback-covered leads)
    # 2.6 Warm: interested + site_visit_planned
    # 2.7 Hot:  site_visit_done + negotiation
    warm_statuses = ['interested', 'site_visit_planned']
    hot_statuses = ['site_visit_done', 'negotiation']

    lead_buckets_base = board_visible
    lead_buckets_base = lead_buckets_base.filter(~Lead.id.in_(db.select(first_callback_lead_ids.c.lead_id)))
    if range_requested:
        lead_buckets_base = lead_scope.filter(~Lead.id.in_(db.select(first_callback_lead_ids.c.lead_id)))

    lead_buckets_base = lead_buckets_base.options(
        joinedload(Lead.project),
        joinedload(Lead.assigned_user),
        joinedload(Lead.sales_manager),
    )

    # New leads should always surface in Action Board within the selected window.
    new_bucket_q = lead_buckets_base.filter(Lead.status == 'new')

    follow_up_q = lead_buckets_base.filter(Lead.status == 'follow_up')
    no_answer_q = lead_buckets_base.filter(Lead.status == 'no_answer')
    warm_q = lead_buckets_base.filter(Lead.status.in_(warm_statuses))
    hot_q = lead_buckets_base.filter(Lead.status.in_(hot_statuses))

    # counts
    current_callbacks_q = unique_cb_base.filter(
        CallbackReminder.callback_datetime >= callback_window_start,
        CallbackReminder.callback_datetime < callback_window_end,
        CallbackReminder.callback_datetime >= datetime.utcnow(),
    )
    overdue_callbacks_q = unique_cb_base.filter(
        CallbackReminder.callback_datetime < datetime.utcnow(),
    )
    today_callbacks_count = current_callbacks_q.count()
    overdue_callbacks_count = overdue_callbacks_q.count()
    new_today_count = new_bucket_q.count()
    follow_up_count = follow_up_q.count()
    no_answer_count = no_answer_q.count()
    warm_count = warm_q.count()
    hot_count = hot_q.count()

    # paged section lists
    current_callbacks_page = _query_page(
        current_callbacks_q,
        section_pages['today_callbacks'],
        CallbackReminder.callback_datetime.asc(),
        CallbackReminder.id.asc(),
    )
    overdue_callbacks_page = _query_page(
        overdue_callbacks_q,
        section_pages['overdue_callbacks'],
        CallbackReminder.callback_datetime.asc(),
        CallbackReminder.id.asc(),
    )
    new_today = _query_page(new_bucket_q, section_pages['new_leads_today'], Lead.created_at.desc(), Lead.id.desc())
    follow_up = _query_page(follow_up_q, section_pages['follow_up'], Lead.updated_at.asc(), Lead.id.asc())
    no_answer = _query_page(no_answer_q, section_pages['no_answer'], Lead.updated_at.asc(), Lead.id.asc())
    warm_leads = _query_page(warm_q, section_pages['warm_leads'], Lead.updated_at.desc(), Lead.id.desc())
    hot_leads = _query_page(hot_q, section_pages['hot_leads'], Lead.updated_at.desc(), Lead.id.desc())

    page_lead_ids = set()
    for cb in current_callbacks_page + overdue_callbacks_page:
        if cb.lead_id:
            page_lead_ids.add(cb.lead_id)
    for lead in new_today + follow_up + no_answer + warm_leads + hot_leads:
        page_lead_ids.add(lead.id)

    latest_notes = {}
    if page_lead_ids:
        latest_note_subq = (
            db.session.query(
                LeadNote.lead_id.label('lead_id'),
                func.max(LeadNote.created_at).label('latest_created_at'),
            )
            .filter(LeadNote.lead_id.in_(list(page_lead_ids)))
            .group_by(LeadNote.lead_id)
            .subquery()
        )
        latest_note_rows = (
            db.session.query(LeadNote.lead_id, LeadNote.note)
            .join(
                latest_note_subq,
                and_(
                    LeadNote.lead_id == latest_note_subq.c.lead_id,
                    LeadNote.created_at == latest_note_subq.c.latest_created_at,
                ),
            )
            .all()
        )
        latest_notes = {row.lead_id: (row.note or '')[:120] for row in latest_note_rows}

    return jsonify({
        'today_callbacks':   [_cb_dict(c) for c in current_callbacks_page],
        'overdue_callbacks':  [_cb_dict(c) for c in overdue_callbacks_page],
        'new_leads_today':   [_lead_card_dict(l) for l in new_today],
        'follow_up_leads':   [_lead_card_dict(l) for l in follow_up],
        'no_answer_leads':   [_lead_card_dict(l) for l in no_answer],
        'warm_leads':        [_lead_card_dict(l) for l in warm_leads],
        'hot_leads':         [_lead_card_dict(l) for l in hot_leads],
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
            'date_from': selected_from_date.isoformat(),
            'date_to': selected_to_date.isoformat(),
            'range_requested': range_requested,
        },
    }), 200


# ---------------------------------------------------------------------------
# Assign / Reassign
# ---------------------------------------------------------------------------

ALL_LEAD_STATUSES = [
    'new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
    'site_visit_planned', 'site_visit_done', 'negotiation', 'booking_done',
    'not_interested', 'lost', 'junk',
]

TERMINAL_LEAD_STATUSES = ['lost', 'junk', 'booking_done', 'not_interested']
PROTECTED_RECYCLE_STATUSES = ['negotiation', 'site_visit_planned']
ACTIVE_REASSIGN_STATUSES = [s for s in ALL_LEAD_STATUSES if s not in TERMINAL_LEAD_STATUSES]
WORKLOAD_STALE_DAYS = 5


def _assignable_users(user):
    """Return list of users this actor can assign leads to."""
    if user.role == 'superadmin':
        return User.query.filter(
            User.tenant_id == user.tenant_id,
            User.is_active == True,
            User.role.in_(['superadmin', 'sales_manager', 'team_member']),
        ).all()
    elif user.role == 'sales_manager':
        team = list(user.team_members)
        team.append(user)  # can assign to self
        return team
    return []


def _ops_lead_dict(lead):
    data = lead.to_dict()
    now = datetime.utcnow()
    created = lead.created_at or now
    updated = lead.updated_at or created
    data['received_at'] = to_ist_str(created)
    data['received_age_hours'] = max(0, int((now - created).total_seconds() // 3600))
    data['received_age_days'] = max(0, (now - created).days)
    data['days_untouched'] = max(0, (now - updated).days)
    data['stale_reason'] = 'No update in {} day{}'.format(
        data['days_untouched'],
        '' if data['days_untouched'] == 1 else 's',
    )
    data['last_action_at'] = to_ist_str(updated)
    data['last_action_label'] = 'Updated' if lead.updated_at else 'Created'
    return data


def _allocation_page_params():
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        raw_size = request.args.get('page_size', request.args.get('per_page', 25))
        per_page = int(raw_size)
    except (TypeError, ValueError):
        per_page = 25
    return page, min(500, max(10, per_page))


def _allocation_project_options(user):
    rows = (
        Project.query
        .with_entities(Project.id, Project.name)
        .filter(Project.tenant_id == user.tenant_id, Project.is_active == True)
        .order_by(Project.name.asc())
        .all()
    )
    return [{'id': pid, 'name': name} for pid, name in rows]


def _allocation_source_options(base_query):
    source_expr = func.lower(func.trim(func.coalesce(Lead.source, '')))
    rows = (
        base_query
        .filter(source_expr != '')
        .with_entities(source_expr.label('value'), func.min(Lead.source).label('label'))
        .group_by(source_expr)
        .order_by(func.min(Lead.source).asc())
        .all()
    )
    return [{'value': value, 'label': label or value} for value, label in rows]


def _apply_allocation_filters(query):
    source = (request.args.get('source') or '').strip().lower()
    project_id = (request.args.get('project_id') or request.args.get('project') or '').strip()
    search = (request.args.get('search') or request.args.get('q') or '').strip().lower()

    if source:
        query = query.filter(func.lower(func.trim(func.coalesce(Lead.source, ''))) == source)
    if project_id:
        try:
            query = query.filter(Lead.project_id == int(project_id))
        except (TypeError, ValueError):
            pass
    if search:
        like_q = f'%{search}%'
        query = query.outerjoin(Project, Lead.project_id == Project.id).filter(or_(
            func.lower(func.coalesce(Lead.name, '')).like(like_q),
            func.lower(func.coalesce(Lead.phone, '')).like(like_q),
            func.lower(func.coalesce(Lead.alternate_phone, '')).like(like_q),
            func.lower(func.coalesce(Project.name, '')).like(like_q),
        ))
    return query


def _allocation_order(query, kind):
    sort = (request.args.get('sort') or '').strip().lower()
    if kind == 'stale':
        if sort == 'stale_asc':
            return query.order_by(Lead.updated_at.desc(), Lead.id.desc())
        return query.order_by(Lead.updated_at.asc(), Lead.id.asc())
    if sort == 'received_asc':
        return query.order_by(Lead.created_at.asc(), Lead.id.asc())
    return query.order_by(Lead.created_at.desc(), Lead.id.desc())


def _allocation_clamped_page(total, page, per_page):
    total_pages = max(1, (total + per_page - 1) // per_page)
    return min(max(1, page), total_pages), total_pages


def _team_scope_ids(user, include_self=True):
    if user.role == 'superadmin':
        rows = User.query.with_entities(User.id).filter(
            User.tenant_id == user.tenant_id,
            User.is_active == True,
            User.role.in_(['superadmin', 'sales_manager', 'team_member']),
        ).all()
        return [r[0] for r in rows]
    if user.role == 'sales_manager':
        ids = [tm.id for tm in user.team_members if tm.is_active]
        if include_self:
            ids.append(user.id)
        return list(dict.fromkeys(ids))
    return [user.id]


def _pending_callback_filter(query, state):
    state = (state or '').strip().lower()
    pending = db.session.query(CallbackReminder.lead_id).filter(
        CallbackReminder.tenant_id == request.current_user.tenant_id,
        CallbackReminder.status == 'pending',
        CallbackReminder.lead_id == Lead.id,
    )
    now = datetime.utcnow()
    today_start, tomorrow_start = business_date_bounds_utc_naive(now_ist().date())
    if state == 'none':
        return query.filter(~pending.exists())
    if state == 'pending':
        return query.filter(pending.exists())
    if state == 'today':
        return query.filter(pending.filter(
            CallbackReminder.callback_datetime >= today_start,
            CallbackReminder.callback_datetime < tomorrow_start,
        ).exists())
    if state == 'overdue':
        return query.filter(pending.filter(CallbackReminder.callback_datetime < now).exists())
    if state == 'future':
        return query.filter(pending.filter(CallbackReminder.callback_datetime >= tomorrow_start).exists())
    return query


def _apply_age_filter(query, bucket):
    bucket = (bucket or '').strip()
    now = datetime.utcnow()
    ranges = {
        '0_3': (now - timedelta(days=3), None),
        '4_7': (now - timedelta(days=7), now - timedelta(days=3)),
        '8_15': (now - timedelta(days=15), now - timedelta(days=7)),
        '16_30': (now - timedelta(days=30), now - timedelta(days=15)),
        '31_plus': (None, now - timedelta(days=30)),
        '0_7': (now - timedelta(days=7), None),
        '31_60': (now - timedelta(days=60), now - timedelta(days=30)),
        '60_plus': (None, now - timedelta(days=60)),
    }
    if bucket not in ranges:
        return query
    newer_than, older_than = ranges[bucket]
    if newer_than:
        query = query.filter(Lead.created_at >= newer_than)
    if older_than:
        query = query.filter(Lead.created_at < older_than)
    return query


def _apply_last_updated_filter(query, bucket):
    bucket = (bucket or '').strip()
    now = datetime.utcnow()
    today_start, tomorrow_start = business_date_bounds_utc_naive(now_ist().date())
    if bucket == 'today':
        return query.filter(Lead.updated_at >= today_start, Lead.updated_at < tomorrow_start)
    days_map = {'1_plus': 1, '3_plus': 3, '7_plus': 7, '15_plus': 15, '30_plus': 30}
    if bucket in days_map:
        return query.filter(Lead.updated_at <= now - timedelta(days=days_map[bucket]))
    return query


def _apply_workload_filters(query, args):
    status = (args.get('status') or args.get('status_filter') or '').strip()
    source = (args.get('source') or '').strip().lower()
    project_id = (args.get('project_id') or args.get('project') or '').strip()
    search = (args.get('search') or args.get('q') or '').strip().lower()
    callback_state = (args.get('callback_state') or '').strip().lower()
    age = (args.get('lead_age') or '').strip()
    last_updated = (args.get('last_updated') or '').strip()
    untouched_only = (args.get('untouched_only') or '').strip().lower() in ('1', 'true', 'yes')
    stale_only = (args.get('stale_only') or '').strip().lower() in ('1', 'true', 'yes')

    if status:
        if status in ALL_LEAD_STATUSES:
            query = query.filter(Lead.status == status)
    else:
        query = query.filter(Lead.status.in_(ACTIVE_REASSIGN_STATUSES))
    if source:
        query = query.filter(func.lower(func.trim(func.coalesce(Lead.source, ''))) == source)
    if project_id:
        try:
            query = query.filter(Lead.project_id == int(project_id))
        except (TypeError, ValueError):
            pass
    if search:
        like_q = f'%{search}%'
        query = query.outerjoin(Project, Lead.project_id == Project.id).filter(or_(
            func.lower(func.coalesce(Lead.name, '')).like(like_q),
            func.lower(func.coalesce(Lead.phone, '')).like(like_q),
            func.lower(func.coalesce(Lead.alternate_phone, '')).like(like_q),
            func.lower(func.coalesce(Project.name, '')).like(like_q),
        ))
    query = _pending_callback_filter(query, callback_state)
    query = _apply_age_filter(query, age)
    query = _apply_last_updated_filter(query, last_updated)
    if untouched_only:
        pending_callback_exists = db.session.query(CallbackReminder.id).filter(
            CallbackReminder.tenant_id == Lead.tenant_id,
            CallbackReminder.lead_id == Lead.id,
            CallbackReminder.status == 'pending',
        ).exists()
        query = query.filter(Lead.status == 'new', ~pending_callback_exists)
    if stale_only:
        query = query.filter(Lead.updated_at <= datetime.utcnow() - timedelta(days=WORKLOAD_STALE_DAYS))
    return query


def _workload_sort(query, args):
    sort = (args.get('sort') or '').strip().lower()
    if sort == 'newest_received':
        return query.order_by(Lead.created_at.desc(), Lead.id.desc())
    if sort == 'most_recently_updated':
        return query.order_by(Lead.updated_at.desc(), Lead.id.desc())
    if sort == 'oldest_callback':
        return query.outerjoin(CallbackReminder, and_(
            CallbackReminder.lead_id == Lead.id,
            CallbackReminder.status == 'pending',
        )).group_by(Lead.id).order_by(func.min(CallbackReminder.callback_datetime).asc().nullslast(), Lead.id.asc())
    if sort == 'least_recently_updated':
        return query.order_by(Lead.updated_at.asc(), Lead.id.asc())
    return query.order_by(Lead.created_at.asc(), Lead.id.asc())


def _lead_callback_state(lead):
    now = datetime.utcnow()
    pending = [cb for cb in (lead.callbacks or []) if cb.status == 'pending']
    if not pending:
        return 'none'
    pending.sort(key=lambda cb: cb.callback_datetime)
    first = pending[0]
    today_start, tomorrow_start = business_date_bounds_utc_naive(now_ist().date())
    if first.callback_datetime < now:
        state = 'overdue'
    elif today_start <= first.callback_datetime < tomorrow_start:
        state = 'today'
    else:
        state = 'future'
    return state


def _workload_preview_dict(lead):
    data = _ops_lead_dict(lead)
    data['callback_state'] = _lead_callback_state(lead)
    data['current_owner_name'] = lead.sales_manager.name if lead.sales_manager else None
    data['assigned_user_name'] = lead.assigned_user.name if lead.assigned_user else None
    return data


def _workload_base_for_user(actor, from_user_id):
    if int(from_user_id) not in _team_scope_ids(actor, include_self=True):
        return None
    return Lead.query.options(
        joinedload(Lead.project),
        joinedload(Lead.assigned_user),
        joinedload(Lead.sales_manager),
        selectinload(Lead.callbacks),
    ).filter(
        Lead.tenant_id == actor.tenant_id,
        Lead.is_active == True,
        Lead.assigned_to == int(from_user_id),
    )


def _eligible_counts_for_query(query, to_user_id=None):
    matching = query.count()
    eligible_q = query
    reasons = {}
    if to_user_id:
        same = eligible_q.filter(Lead.assigned_to == int(to_user_id)).count()
        if same:
            reasons['already_assigned_to_destination'] = same
            eligible_q = eligible_q.filter(Lead.assigned_to != int(to_user_id))
    eligible = eligible_q.count()
    excluded = max(0, matching - eligible)
    return matching, eligible, excluded, reasons, eligible_q


@leads_bp.route('/assign-reassign/unassigned', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def ar_unassigned():
    """Leads with no assignee."""
    user = request.current_user
    q = Lead.query.filter(
        Lead.tenant_id == user.tenant_id,
        Lead.is_active == True,
        Lead.assigned_to == None,
    )
    if user.role == 'sales_manager':
        # Only unassigned leads visible to this manager's scope (by sales_manager_id)
        q = q.filter(
            db.or_(
                Lead.sales_manager_id == user.id,
                Lead.sales_manager_id == None,
            )
        )

    source_options = _allocation_source_options(q)
    project_options = _allocation_project_options(user)
    q = _apply_allocation_filters(q)
    page, per_page = _allocation_page_params()
    total = q.count()
    page, total_pages = _allocation_clamped_page(total, page, per_page)
    ordered_q = _allocation_order(q, 'unassigned')
    ids_only = (request.args.get('ids_only') or '').strip().lower() in ('1', 'true', 'yes')
    if ids_only:
        try:
            limit = max(1, min(10000, int(request.args.get('limit', 10000))))
        except (TypeError, ValueError):
            limit = 10000
        id_rows = (
            ordered_q.with_entities(Lead.id)
            .limit(limit)
            .all()
        )
        assignable = _assignable_users(user)
        return jsonify({
            'lead_ids': [row[0] for row in id_rows],
            'total': total,
            'limit': limit,
            'limited': total > limit,
            'assignable_users': [{'id': u.id, 'name': u.name, 'role': u.role} for u in assignable],
            'filters': {'sources': source_options, 'projects': project_options},
        }), 200
    leads = ordered_q.offset((page - 1) * per_page).limit(per_page).all()
    assignable = _assignable_users(user)
    return jsonify({
        'leads': [_ops_lead_dict(l) for l in leads],
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'filters': {'sources': source_options, 'projects': project_options},
        'assignable_users': [{'id': u.id, 'name': u.name, 'role': u.role} for u in assignable],
    }), 200


@leads_bp.route('/assign-reassign/stale', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def ar_stale():
    """Leads not updated in N days."""
    user = request.current_user
    try:
        days = max(1, min(90, int(request.args.get('days', 5))))
    except (TypeError, ValueError):
        days = 5
    status_filter = request.args.get('status', '').strip()
    cutoff = datetime.utcnow() - timedelta(days=days)

    if user.role == 'superadmin':
        q = Lead.query.filter(
            Lead.tenant_id == user.tenant_id,
            Lead.is_active == True,
            Lead.updated_at <= cutoff,
            Lead.assigned_to != None,
        )
    else:
        team_ids = [tm.id for tm in user.team_members]
        team_ids.append(user.id)
        q = Lead.query.filter(
            Lead.tenant_id == user.tenant_id,
            Lead.is_active == True,
            Lead.updated_at <= cutoff,
            Lead.assigned_to.in_(team_ids),
        )

    if status_filter and status_filter in ALL_LEAD_STATUSES:
        q = q.filter(Lead.status == status_filter)

    source_options = _allocation_source_options(q)
    project_options = _allocation_project_options(user)
    q = _apply_allocation_filters(q)
    page, per_page = _allocation_page_params()
    total = q.count()
    page, total_pages = _allocation_clamped_page(total, page, per_page)
    ordered_q = _allocation_order(q, 'stale')
    ids_only = (request.args.get('ids_only') or '').strip().lower() in ('1', 'true', 'yes')
    if ids_only:
        try:
            limit = max(1, min(10000, int(request.args.get('limit', 10000))))
        except (TypeError, ValueError):
            limit = 10000
        id_rows = ordered_q.with_entities(Lead.id).limit(limit).all()
        assignable = _assignable_users(user)
        return jsonify({
            'lead_ids': [row[0] for row in id_rows],
            'total': total,
            'limit': limit,
            'limited': total > limit,
            'days': days,
            'filters': {'sources': source_options, 'projects': project_options},
            'assignable_users': [{'id': u.id, 'name': u.name, 'role': u.role} for u in assignable],
        }), 200
    leads = ordered_q.offset((page - 1) * per_page).limit(per_page).all()
    assignable = _assignable_users(user)
    return jsonify({
        'leads': [_ops_lead_dict(l) for l in leads],
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'days': days,
        'filters': {'sources': source_options, 'projects': project_options},
        'assignable_users': [{'id': u.id, 'name': u.name, 'role': u.role} for u in assignable],
    }), 200


@leads_bp.route('/assign-reassign/workload', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def ar_workload():
    """Per-member active lead counts."""
    user = request.current_user
    if user.role == 'superadmin':
        members = User.query.filter(
            User.tenant_id == user.tenant_id,
            User.is_active == True,
            User.role.in_(['sales_manager', 'team_member']),
        ).all()
    else:
        members = list(user.team_members)
        members.append(user)

    stale_cutoff = datetime.utcnow() - timedelta(days=WORKLOAD_STALE_DAYS)
    result = []
    for m in members:
        member_base = Lead.query.filter(
            Lead.tenant_id == user.tenant_id,
            Lead.is_active == True,
            Lead.assigned_to == m.id,
        )
        total = member_base.count()
        active = member_base.filter(
            Lead.status.notin_(TERMINAL_LEAD_STATUSES),
        ).count()
        pending_callback_exists = db.session.query(CallbackReminder.id).filter(
            CallbackReminder.tenant_id == user.tenant_id,
            CallbackReminder.lead_id == Lead.id,
            CallbackReminder.status == 'pending',
        ).exists()
        untouched = member_base.filter(
            Lead.status == 'new',
            ~pending_callback_exists,
        ).count()
        follow_ups = member_base.filter(Lead.status == 'follow_up').count()
        stale = member_base.filter(
            Lead.status.notin_(TERMINAL_LEAD_STATUSES),
            Lead.updated_at <= stale_cutoff,
        ).count()
        callback_base = db.session.query(func.count(func.distinct(Lead.id))).join(
            CallbackReminder,
            and_(
                CallbackReminder.lead_id == Lead.id,
                CallbackReminder.tenant_id == user.tenant_id,
                CallbackReminder.status == 'pending',
            ),
        ).filter(
            Lead.tenant_id == user.tenant_id,
            Lead.is_active == True,
            Lead.assigned_to == m.id,
        )
        pending_cb = callback_base.scalar() or 0
        overdue_cb = callback_base.filter(
            CallbackReminder.callback_datetime < datetime.utcnow(),
        ).scalar() or 0
        legacy_pending_cb = db.session.query(func.count(func.distinct(CallbackReminder.lead_id))).filter(
            CallbackReminder.tenant_id == user.tenant_id,
            CallbackReminder.assigned_user_id == m.id,
            CallbackReminder.status == 'pending',
        ).scalar() or 0
        orphaned_callback_delta = max(0, legacy_pending_cb - pending_cb)
        result.append({
            'id': m.id, 'name': m.name, 'role': m.role,
            'total_leads': total, 'active_leads': active,
            'assigned': total,
            'untouched': untouched,
            'callbacks': pending_cb,
            'overdue_callbacks': overdue_cb,
            'stale': stale,
            'follow_ups': follow_ups,
            'legacy_callback_delta': orphaned_callback_delta,
        })
    result.sort(key=lambda x: x['active_leads'], reverse=True)
    assignable = _assignable_users(user)
    return jsonify({
        'members': result,
        'definitions': {
            'assigned': 'Active visible leads currently assigned to the member.',
            'untouched': 'Active assigned leads still in New status with no pending callback.',
            'callbacks': 'Distinct active current-assignee leads with pending callbacks.',
            'overdue_callbacks': 'Distinct active current-assignee leads with pending callbacks before now.',
            'stale': f'Active non-terminal assigned leads not updated in {WORKLOAD_STALE_DAYS}+ days.',
            'follow_ups': 'Active assigned leads in Follow Up status.',
        },
        'assignable_users': [{'id': u.id, 'name': u.name, 'role': u.role} for u in assignable],
        'filters': {
            'sources': _allocation_source_options(Lead.query.filter(Lead.tenant_id == user.tenant_id, Lead.is_active == True)),
            'projects': _allocation_project_options(user),
            'statuses': ALL_LEAD_STATUSES,
        },
    }), 200


@leads_bp.route('/assign-reassign/workload-preview', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def ar_workload_preview():
    user = request.current_user
    from_id = request.args.get('from_user_id')
    if not from_id or not str(from_id).isdigit():
        return jsonify({'error': 'from_user_id is required'}), 400
    base = _workload_base_for_user(user, int(from_id))
    if base is None:
        return jsonify({'error': 'Source user outside your scope'}), 403
    filtered = _apply_workload_filters(base, request.args)
    to_user_id = request.args.get('to_user_id')
    matching, eligible, excluded, reasons, eligible_q = _eligible_counts_for_query(filtered, to_user_id if to_user_id and str(to_user_id).isdigit() else None)
    page, per_page = _allocation_page_params()
    page, total_pages = _allocation_clamped_page(eligible, page, per_page)
    preview_q = _workload_sort(eligible_q, request.args)
    leads = preview_q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'matching': matching,
        'eligible': eligible,
        'excluded': excluded,
        'exclusion_reasons': reasons,
        'leads': [_workload_preview_dict(l) for l in leads],
        'page': page,
        'per_page': per_page,
        'total_pages': total_pages,
        'max_rows_returned': per_page,
        'filters': {
            'sources': _allocation_source_options(Lead.query.filter(Lead.tenant_id == user.tenant_id, Lead.is_active == True)),
            'projects': _allocation_project_options(user),
            'statuses': ALL_LEAD_STATUSES,
        },
    }), 200


@leads_bp.route('/assign-reassign/bulk-assign', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def ar_bulk_assign():
    """Bulk assign or reassign leads to a target user."""
    user = request.current_user
    data = request.get_json() or {}
    operation_correlation = request_correlation_id(request)
    lead_ids = [int(x) for x in (data.get('lead_ids') or []) if str(x).isdigit()]
    target_id = data.get('target_user_id')
    if not lead_ids:
        return jsonify({'error': 'lead_ids required'}), 400
    if not target_id:
        return jsonify({'error': 'target_user_id required'}), 400

    target = User.query.filter_by(id=int(target_id), tenant_id=user.tenant_id, is_active=True).first()
    if not target:
        return jsonify({'error': 'Target user not found'}), 404

    # Permission check
    if user.role == 'sales_manager':
        allowed_ids = [tm.id for tm in user.team_members] + [user.id]
        if target.id not in allowed_ids:
            return jsonify({'error': 'Cannot assign to users outside your team'}), 403

    leads_q = Lead.query.filter(
        Lead.tenant_id == user.tenant_id,
        Lead.is_active == True,
        Lead.id.in_(lead_ids),
    )
    if user.role == 'sales_manager':
        allowed_lead_ids = [tm.id for tm in user.team_members] + [user.id]
        leads_q = leads_q.filter(
            db.or_(
                Lead.assigned_to.in_(allowed_lead_ids),
                Lead.assigned_to.is_(None),
            )
        )

    leads_by_id = {lead.id: lead for lead in leads_q.all()}

    assigned = 0
    for lid in lead_ids:
        lead = leads_by_id.get(lid)
        if not lead:
            continue
        old_assignee = lead.assigned_to
        lead.assigned_to = target.id
        db.session.add(LeadAssignmentHistory(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            assigned_from=old_assignee,
            assigned_to=target.id,
            assigned_by=user.id,
            reason=data.get('reason', 'Bulk assign/reassign'),
            source='ALLOCATION_BULK_ASSIGN',
            correlation_id=operation_correlation,
        ))
        log_activity(
            user.id, 'assign_lead', 'leads', lead.id, 'Lead',
            description=f'Bulk assigned lead {lead.name} to {target.name}',
            tenant_id=lead.tenant_id,
            correlation_id=operation_correlation,
        )
        assigned += 1

    db.session.commit()

    # Notify assignee
    if assigned > 0 and target.id != user.id:
        push_notification(target.id, {
            'type': 'lead_assigned',
            'kind': 'info',
            'title': 'New Leads Assigned',
            'message': f'📋 {assigned} lead{"s" if assigned != 1 else ""} {"have" if assigned != 1 else "has"} been assigned to you by {user.name}.',
            'source': 'ar_bulk_assignment',
            'tenant_id': target.tenant_id,
            'correlation_id': operation_correlation,
        })
        try:
            from app.services.notification_events import enqueue_lead_assigned
            first_lead = Lead.query.filter_by(id=lead_ids[0], tenant_id=user.tenant_id).first() if lead_ids else None
            if first_lead:
                ev = enqueue_lead_assigned(
                    target, first_lead,
                    correlation_id=operation_correlation,
                    idempotency_key=(
                        f'allocation-bulk:{operation_correlation}:'
                        f'user:{target.id}'
                    ),
                )
                ev.title = 'New Leads Assigned'
                ev.body = f'{assigned} new lead{"s" if assigned != 1 else ""} assigned to you'
                db.session.commit()
        except Exception:
            db.session.rollback()

    return jsonify({'assigned': assigned, 'total_requested': len(lead_ids)}), 200
@leads_bp.route('/assign-reassign/workload-move', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def ar_workload_move():
    """Move filtered active leads from one member to another."""
    user = request.current_user
    data = request.get_json() or {}
    operation_correlation = request_correlation_id(request)
    from_id = data.get('from_user_id')
    to_id = data.get('to_user_id')
    try:
        count = max(1, min(500, int(data.get('count', 10))))
    except (TypeError, ValueError):
        count = 10

    if not from_id or not to_id:
        return jsonify({'error': 'from_user_id and to_user_id required'}), 400
    if int(from_id) == int(to_id):
        return jsonify({'error': 'Source and destination cannot be the same'}), 400

    from_user = User.query.filter_by(id=int(from_id), tenant_id=user.tenant_id, is_active=True).first()
    to_user = User.query.filter_by(id=int(to_id), tenant_id=user.tenant_id, is_active=True).first()
    if not from_user or not to_user:
        return jsonify({'error': 'User not found'}), 404

    if user.role == 'sales_manager':
        allowed_ids = [tm.id for tm in user.team_members] + [user.id]
        if from_user.id not in allowed_ids or to_user.id not in allowed_ids:
            return jsonify({'error': 'Users outside your team'}), 403

    base = _workload_base_for_user(user, from_user.id)
    if base is None:
        return jsonify({'error': 'Source user outside your scope'}), 403
    filter_args = dict(data)
    if 'status_filter' in filter_args and 'status' not in filter_args:
        filter_args['status'] = filter_args.get('status_filter')
    filtered = _apply_workload_filters(base, filter_args)
    matching, eligible, excluded, reasons, eligible_q = _eligible_counts_for_query(filtered, to_user.id)
    ordered_q = _workload_sort(eligible_q, filter_args)

    mode = (data.get('selection_mode') or 'first_n').strip().lower()
    selected_ids = [int(x) for x in (data.get('lead_ids') or []) if str(x).isdigit()]
    if mode == 'selected':
        if not selected_ids:
            return jsonify({'error': 'lead_ids required for selected mode'}), 400
        leads = ordered_q.filter(Lead.id.in_(selected_ids)).limit(500).all()
    elif mode == 'current_page':
        page = max(1, int(data.get('page') or 1))
        per_page = min(500, max(1, int(data.get('per_page') or data.get('page_size') or count)))
        leads = ordered_q.offset((page - 1) * per_page).limit(per_page).all()
    elif mode == 'all':
        leads = ordered_q.limit(500).all()
        if eligible > 500:
            reasons['sync_cap_500'] = eligible - 500
    elif mode == 'random_n':
        id_rows = ordered_q.with_entities(Lead.id).limit(2000).all()
        ids = [row[0] for row in id_rows]
        chosen = set(random.sample(ids, min(count, len(ids)))) if ids else set()
        leads = ordered_q.filter(Lead.id.in_(chosen)).all() if chosen else []
    else:
        leads = ordered_q.limit(count).all()

    moved = 0
    skipped = max(0, eligible - len(leads)) if mode in ('all', 'random_n', 'first_n') else 0
    moved_ids = []
    for lead in leads:
        if not lead.is_active or lead.assigned_to != from_user.id:
            continue
        lead.assigned_to = to_user.id
        db.session.add(LeadAssignmentHistory(
            tenant_id=lead.tenant_id,
            lead_id=lead.id,
            assigned_from=from_user.id,
            assigned_to=to_user.id,
            assigned_by=user.id,
            reason='Workload rebalance',
            source='WORKLOAD_REBALANCE',
            correlation_id=operation_correlation,
        ))
        log_activity(
            user.id, 'assign_lead', 'leads', lead.id, 'Lead',
            description=(
                f'Workload move: {lead.name} from '
                f'{from_user.name} to {to_user.name}'
            ),
            tenant_id=lead.tenant_id,
            correlation_id=operation_correlation,
        )
        CallbackReminder.query.filter(
            CallbackReminder.tenant_id == user.tenant_id,
            CallbackReminder.lead_id == lead.id,
            CallbackReminder.status == 'pending',
        ).update({'assigned_user_id': to_user.id}, synchronize_session=False)
        moved += 1
        moved_ids.append(lead.id)

    db.session.commit()

    # Notify the new assignee
    if moved > 0 and to_user.id != user.id:
        push_notification(to_user.id, {
            'type': 'lead_assigned',
            'kind': 'info',
            'title': 'Leads Transferred to You',
            'message': f'📋 {moved} lead{"s" if moved != 1 else ""} from {from_user.name} {"have" if moved != 1 else "has"} been transferred to you by {user.name}.',
            'source': 'workload_move',
            'tenant_id': to_user.tenant_id,
            'correlation_id': operation_correlation,
        })
        try:
            from app.services.notification_events import enqueue_lead_assigned
            if leads:
                ev = enqueue_lead_assigned(
                    to_user, leads[0],
                    correlation_id=operation_correlation,
                    idempotency_key=(
                        f'workload-move:{operation_correlation}:'
                        f'user:{to_user.id}'
                    ),
                )
                ev.title = 'Leads Transferred to You'
                ev.body = f'{moved} lead{"s" if moved != 1 else ""} transferred from {from_user.name}'
                db.session.commit()
        except Exception:
            db.session.rollback()

    return jsonify({
        'requested_count': count if mode in ('first_n', 'random_n') else len(selected_ids) if mode == 'selected' else eligible,
        'matching': matching,
        'eligible': eligible,
        'excluded': excluded,
        'moved': moved,
        'skipped': skipped,
        'error_count': 0,
        'skip_reasons': reasons,
        'moved_ids': moved_ids,
        'selection_mode': mode,
    }), 200
# ---------------------------------------------------------------------------

RECYCLE_STATUSES = [
    'new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
    'site_visit_planned', 'site_visit_done', 'negotiation', 'booking_done',
    'not_interested', 'lost', 'junk',
]


def _apply_recycle_filters(query, user, args):
    owner = (args.get('owner_id') or args.get('assigned_to') or '').strip()
    status = (args.get('status') or '').strip()
    source = (args.get('source') or '').strip().lower()
    project_id = (args.get('project_id') or args.get('project') or '').strip()
    search = (args.get('q') or args.get('search') or '').strip().lower()
    callback_state = (args.get('callback_state') or '').strip().lower()
    lead_age = (args.get('lead_age') or '').strip()
    untouched_only = (args.get('untouched_only') or '').strip().lower() in ('1', 'true', 'yes')

    if owner == 'unassigned':
        query = query.filter(Lead.assigned_to == None)
    elif owner:
        try:
            owner_id = int(owner)
            if owner_id in _team_scope_ids(user, include_self=True):
                query = query.filter(Lead.assigned_to == owner_id)
        except (TypeError, ValueError):
            pass
    if status and status in RECYCLE_STATUSES:
        query = query.filter(Lead.status == status)
    if source:
        query = query.filter(func.lower(func.trim(func.coalesce(Lead.source, ''))) == source)
    if project_id:
        try:
            query = query.filter(Lead.project_id == int(project_id))
        except (TypeError, ValueError):
            pass
    if search:
        like_q = f'%{search}%'
        query = query.outerjoin(User, Lead.assigned_to == User.id).outerjoin(Project, Lead.project_id == Project.id).filter(
            or_(
                func.lower(func.coalesce(Lead.name, '')).like(like_q),
                func.lower(func.coalesce(Lead.phone, '')).like(like_q),
                func.lower(func.coalesce(Project.name, '')).like(like_q),
                func.lower(func.coalesce(User.name, '')).like(like_q),
            )
        )
    query = _pending_callback_filter(query, callback_state)
    query = _apply_age_filter(query, lead_age)
    if untouched_only:
        query = query.filter(Lead.status == 'new')
    return query


def _apply_recycle_stale_window(query):
    stale_mode = (request.args.get('stale_mode') or '').strip().lower()
    now = datetime.utcnow()
    if stale_mode in ('3', '3_plus'):
        return query.filter(Lead.updated_at <= now - timedelta(days=3)), '3_plus'
    if stale_mode in ('7', '7_plus'):
        return query.filter(Lead.updated_at <= now - timedelta(days=7)), '7_plus'
    if stale_mode in ('15', '15_plus'):
        return query.filter(Lead.updated_at <= now - timedelta(days=15)), '15_plus'
    if stale_mode in ('30', '30_plus'):
        return query.filter(Lead.updated_at <= now - timedelta(days=30)), '30_plus'
    if stale_mode == 'yesterday':
        today_start, _ = business_date_bounds_utc_naive(now_ist().date())
        yesterday_start = today_start - timedelta(days=1)
        return query.filter(Lead.updated_at >= yesterday_start, Lead.updated_at < today_start), 'yesterday'
    return query.filter(Lead.updated_at <= now - timedelta(days=5)), '5_plus'


def _recycle_eligibility_parts(query, cooldown_days=7):
    reasons = {}
    eligible_q = query
    terminal = query.filter(Lead.status.in_(TERMINAL_LEAD_STATUSES)).count()
    if terminal:
        reasons['terminal_status'] = terminal
        eligible_q = eligible_q.filter(Lead.status.notin_(TERMINAL_LEAD_STATUSES))
    protected = eligible_q.filter(Lead.status.in_(PROTECTED_RECYCLE_STATUSES)).count()
    if protected:
        reasons['protected_stage'] = protected
        eligible_q = eligible_q.filter(Lead.status.notin_(PROTECTED_RECYCLE_STATUSES))
    future_exists = _recycle_future_callback_exists()
    future_pending = eligible_q.filter(future_exists.exists()).count()
    if future_pending:
        reasons['future_pending_callback'] = future_pending
        eligible_q = eligible_q.filter(~future_exists.exists())
    cooldown_exists = _recycle_cooldown_exists(cooldown_days)
    cooldown = eligible_q.filter(cooldown_exists.exists()).count()
    if cooldown:
        reasons['inside_cooldown'] = cooldown
        eligible_q = eligible_q.filter(~cooldown_exists.exists())
    return eligible_q, reasons


def _recycle_future_callback_exists():
    return db.session.query(CallbackReminder.id).filter(
        CallbackReminder.lead_id == Lead.id,
        CallbackReminder.status == 'pending',
        CallbackReminder.callback_datetime > datetime.utcnow(),
    )


def _recycle_cooldown_exists(cooldown_days=7):
    cooldown_cutoff = datetime.utcnow() - timedelta(days=max(1, int(cooldown_days or 7)))
    return db.session.query(LeadAssignmentHistory.id).filter(
        LeadAssignmentHistory.lead_id == Lead.id,
        LeadAssignmentHistory.assigned_at >= cooldown_cutoff,
    )


def _recycle_history_exists():
    return db.session.query(LeadAssignmentHistory.id).filter(
        LeadAssignmentHistory.lead_id == Lead.id,
    )


def _recycle_sort(query):
    sort = (request.args.get('sort') or '').strip().lower()
    if sort == 'highest_reassignment':
        history_count = (
            db.session.query(
                LeadAssignmentHistory.lead_id.label('lead_id'),
                func.count(LeadAssignmentHistory.id).label('reassignment_count'),
            )
            .group_by(LeadAssignmentHistory.lead_id)
            .subquery()
        )
        return (
            query.outerjoin(history_count, history_count.c.lead_id == Lead.id)
            .order_by(func.coalesce(history_count.c.reassignment_count, 0).desc(), Lead.updated_at.asc(), Lead.id.asc())
        )
    if sort == 'recently_stale':
        return query.order_by(Lead.updated_at.desc(), Lead.id.desc())
    if sort == 'oldest_received':
        return query.order_by(Lead.created_at.asc(), Lead.id.asc())
    if sort == 'newest_received':
        return query.order_by(Lead.created_at.desc(), Lead.id.desc())
    return query.order_by(Lead.updated_at.asc(), Lead.id.asc())


@leads_bp.route('/recycle-queue', methods=['GET'])
@require_role('superadmin', 'sales_manager')
def recycle_queue():
    """Return leads eligible for recycling/reshuffling."""
    user = request.current_user
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get('page_size', 25))
    except (TypeError, ValueError):
        page_size = 25
    page_size = max(1, min(500, page_size))
    view = (request.args.get('view') or 'eligible').strip().lower()
    try:
        cooldown_days = max(1, int(request.args.get('cooldown_days', 7)))
    except (TypeError, ValueError):
        cooldown_days = 7

    base = get_user_visible_leads(user).options(
        joinedload(Lead.project),
        joinedload(Lead.assigned_user),
        selectinload(Lead.callbacks),
    ).filter(Lead.is_active == True)
    base, stale_mode = _apply_recycle_stale_window(base)
    filtered = _apply_recycle_filters(base, user, request.args)
    matching = filtered.count()
    eligible_q, reasons = _recycle_eligibility_parts(filtered, cooldown_days)
    eligible = eligible_q.count()
    excluded = max(0, matching - eligible)
    if view == 'excluded':
        page_query = filtered.filter(~Lead.id.in_(eligible_q.with_entities(Lead.id)))
        total = excluded
    elif view == 'inside_cooldown':
        page_query = filtered.filter(_recycle_cooldown_exists(cooldown_days).exists())
        total = page_query.count()
    elif view == 'previously_reassigned':
        page_query = filtered.filter(_recycle_history_exists().exists())
        total = page_query.count()
    else:
        page_query = eligible_q
        total = eligible
    page, total_pages = _allocation_clamped_page(total, page, page_size)
    offset = (page - 1) * page_size
    leads = _recycle_sort(page_query).offset(offset).limit(page_size).all()

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
        d['reassignment_count'] = len(prev)
        d['callback_state'] = _lead_callback_state(lead)
        d['eligible'] = view == 'eligible'
        d['exclusion_reason'] = None
        if view == 'excluded':
            if lead.status in TERMINAL_LEAD_STATUSES:
                d['exclusion_reason'] = 'terminal_status'
            elif lead.status in PROTECTED_RECYCLE_STATUSES:
                d['exclusion_reason'] = 'protected_stage'
            elif any(cb.status == 'pending' and cb.callback_datetime > datetime.utcnow() for cb in (lead.callbacks or [])):
                d['exclusion_reason'] = 'future_pending_callback'
            else:
                d['exclusion_reason'] = 'inside_cooldown_or_other'
        elif view == 'inside_cooldown':
            d['exclusion_reason'] = 'inside_cooldown'
        elif view == 'previously_reassigned':
            d['exclusion_reason'] = 'previously_reassigned'
        return d

    return jsonify({
        'leads':      [_with_history(l) for l in leads],
        'total':      total,
        'matching':   matching,
        'eligible':   eligible,
        'excluded':   excluded,
        'exclusion_reasons': reasons,
        'page':       page,
        'page_size':  page_size,
        'total_pages': total_pages,
        'view': view,
        'stale_mode': stale_mode or 'older_than_days',
        'filters': {
            'sources': _allocation_source_options(get_user_visible_leads(user).filter(Lead.is_active == True)),
            'projects': _allocation_project_options(user),
            'users': [{'id': u.id, 'name': u.name, 'role': u.role} for u in _assignable_users(user)],
            'statuses': RECYCLE_STATUSES,
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
    if len(lead_ids) > 500:
        return jsonify({'error': 'Max 500 leads per reshuffle'}), 400
    visible = get_user_visible_leads(user).filter(
        Lead.id.in_([int(x) for x in lead_ids if str(x).isdigit()]),
        Lead.is_active == True,
    )
    eligible_q, skip_reasons = _recycle_eligibility_parts(visible, cooldown_days)
    eligible_ids = [row[0] for row in eligible_q.with_entities(Lead.id).all()]
    skipped_count = max(0, len(lead_ids) - len(eligible_ids))
    lead_ids = eligible_ids
    if not lead_ids:
        return jsonify({
            'error': 'No eligible leads selected',
            'skipped': skipped_count,
            'skip_reasons': skip_reasons,
        }), 400

    queued = len(lead_ids) > 50 or request.args.get('async', '').strip() == '1'

    job = LeadReshuffleJob(
        tenant_id=user.tenant_id,
        user_id=user.id,
        lead_ids=lead_ids,
        strategy=strategy,
        reason=reason,
        cooldown_days=cooldown_days,
        status='queued' if queued else 'processing',
        started_at=datetime.utcnow() if not queued else None,
    )
    db.session.add(job)
    db.session.flush()

    if queued:
        db.session.commit()
        return jsonify({
            'job': job.to_dict(),
            'status': 'queued',
            'skipped': skipped_count,
            'skip_reasons': skip_reasons,
        }), 202

    # Gather eligible team members
    if user.role == 'sales_manager':
        team = User.query.filter_by(manager_id=user.id, is_active=True).all()
    else:  # superadmin
        team = User.query.filter_by(role='team_member', tenant_id=user.tenant_id, is_active=True).all()

    if not team:
        return jsonify({'error': 'No active team members available'}), 400

    result = _process_reshuffle_job(job, user, team, strategy, reason, cooldown_days)
    result['skipped'] = skipped_count
    result['skip_reasons'] = skip_reasons
    return jsonify(result), 200


@leads_bp.route('/reshuffle/jobs/<int:job_id>/process', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def process_reshuffle_job(job_id):
    job = LeadReshuffleJob.query.get(job_id)
    user = request.current_user
    if not job or job.tenant_id != user.tenant_id:
        return jsonify({'error': 'Job not found'}), 404
    if job.user_id != user.id and user.role not in ('sales_manager', 'superadmin'):
        return jsonify({'error': 'Forbidden'}), 403

    if user.role == 'sales_manager':
        team = User.query.filter_by(manager_id=user.id, is_active=True).all()
    else:
        team = User.query.filter_by(role='team_member', tenant_id=user.tenant_id, is_active=True).all()

    if not team:
        return jsonify({'error': 'No active team members available'}), 400

    return jsonify(_process_reshuffle_job(job, user, team, job.strategy, job.reason, job.cooldown_days)), 200


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


def _timeline_iso(dt_value):
    if not dt_value:
        return None
    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def _timeline_event(event_type, title, occurred_at, actor_name=None, details=None, payload=None):
    return {
        'type': event_type,
        'title': title,
        'occurred_at': _timeline_iso(occurred_at),
        'occurred_at_ist': to_ist_str(occurred_at),
        'actor_name': actor_name,
        'details': details,
        'payload': payload or {},
    }


@leads_bp.route('/<int:lead_id>/detail-bundle', methods=['GET'])
@require_auth
def get_lead_detail_bundle(lead_id):
    user = request.current_user
    lead = Lead.query.get(lead_id)
    err = _check_lead_access(user, lead)
    if err:
        return err

    notes = (
        LeadNote.query
        .filter_by(lead_id=lead_id)
        .order_by(LeadNote.created_at.desc())
        .all()
    )
    status_history = (
        StatusHistory.query
        .filter_by(lead_id=lead_id)
        .order_by(StatusHistory.changed_at.desc())
        .all()
    )
    assignment_history = (
        LeadAssignmentHistory.query
        .filter_by(lead_id=lead_id)
        .order_by(LeadAssignmentHistory.assigned_at.desc())
        .all()
    )
    callbacks = (
        CallbackReminder.query
        .filter_by(lead_id=lead_id)
        .order_by(CallbackReminder.callback_datetime.asc())
        .all()
    )
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

    latest_ingestion = (
        IngestedLeadLog.query
        .filter_by(tenant_id=lead.tenant_id, lead_id=lead_id)
        .order_by(IngestedLeadLog.received_at.desc())
        .first()
    )
    acquisition = None
    if latest_ingestion:
        acquisition = {
            'source_type': latest_ingestion.source_type,
            'platform_lead_id': latest_ingestion.platform_lead_id,
            'campaign_id': latest_ingestion.campaign_id,
            'campaign_name': latest_ingestion.campaign_name,
            'ad_set_id': latest_ingestion.ad_set_id,
            'ad_set_name': latest_ingestion.ad_set_name,
            'ad_id': latest_ingestion.ad_id,
            'ad_name': latest_ingestion.ad_name,
            'form_id': latest_ingestion.form_id,
            'form_name': latest_ingestion.form_name,
            'page_id': latest_ingestion.page_id,
            'mapped_fields': latest_ingestion.mapped_fields or {},
            'received_at': latest_ingestion.received_at.isoformat() if latest_ingestion.received_at else None,
        }

    timeline_events = []
    if lead.created_at:
        timeline_events.append(_timeline_event(
            'lead_created',
            'Lead created',
            lead.created_at,
            actor_name=lead.creator.name if lead.creator else None,
            details='Lead entered the LMS',
        ))
    for note in notes:
        timeline_events.append(_timeline_event(
            'note',
            'Note added',
            note.created_at,
            actor_name=note.creator.name if note.creator else None,
            details=note.note,
            payload=note.to_dict(),
        ))
    for hist in status_history:
        timeline_events.append(_timeline_event(
            'status',
            'Status changed',
            hist.changed_at,
            actor_name=hist.changed_by_user.name if hist.changed_by_user else None,
            details=f'{hist.old_status or "None"} to {hist.new_status}',
            payload=hist.to_dict(),
        ))
    for hist in assignment_history:
        timeline_events.append(_timeline_event(
            'assign',
            'Lead assigned',
            hist.assigned_at,
            actor_name=hist.assigned_by_user.name if hist.assigned_by_user else None,
            details=f'{hist.assigned_from_user.name if hist.assigned_from_user else "Unassigned"} to {hist.assigned_to_user.name if hist.assigned_to_user else "Unassigned"}',
            payload=hist.to_dict(),
        ))
    for log in call_logs:
        timeline_events.append(_timeline_event(
            'activity',
            'Call activity',
            log.created_at,
            actor_name=log.user.name if log.user else None,
            details=log.description,
            payload=log.to_dict(),
        ))
    for cb in callbacks:
        timeline_events.append(_timeline_event(
            'callback',
            'Callback',
            cb.callback_datetime,
            actor_name=cb.creator.name if cb.creator else None,
            details=cb.notes,
            payload=cb.to_dict(),
        ))
    timeline_events.sort(key=lambda item: item.get('occurred_at') or '', reverse=True)

    return jsonify({
        'lead': lead.to_dict(),
        'acquisition': acquisition,
        'notes': [n.to_dict() for n in notes],
        'status_history': [h.to_dict() for h in status_history],
        'assignment_history': [h.to_dict() for h in assignment_history],
        'callbacks': [c.to_dict() for c in callbacks],
        'call_activities': [log.to_dict() for log in call_logs],
        'timeline_events': timeline_events,
    }), 200


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
        cb, existing_pending, pending_error = create_callback_for_lead(
            lead,
            user,
            raw_dt,
            notes=data.get('notes', ''),
            correlation_id=request_correlation_id(request),
        )
    except ValueError as exc:
        message = str(exc) or 'Invalid datetime format. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS)'
        status_code = 400
        if 'future' in message.lower():
            return jsonify({'error': message}), status_code
        return jsonify({'error': 'Invalid datetime format. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS)'}), status_code
    if pending_error:
        return jsonify({
            'error': pending_error or CALLBACK_PENDING_ERROR,
            'pending_callback': existing_pending.to_dict(),
        }), 409

    db.session.commit()

    log_activity(
        user.id, 'create_callback', 'leads', lead_id, 'Lead',
        description=f'Scheduled callback for lead {lead.name} at {_format_ist_datetime(cb.callback_datetime)}',
        tenant_id=lead.tenant_id,
        correlation_id=cb.correlation_id,
    )
    return jsonify({'callback': cb.to_dict()}), 201


@leads_bp.route('/callbacks/<int:callback_id>/complete', methods=['POST'])
@require_auth
def complete_callback(callback_id):
    user = request.current_user
    cb = CallbackReminder.query.get(callback_id)
    if not cb or cb.tenant_id != user.tenant_id:
        return jsonify({'error': 'Callback not found'}), 404

    if cb.status != 'pending':
        return jsonify({'error': 'Only pending callbacks can be closed'}), 400

    data = request.get_json() or {}
    closure_note = (data.get('closure_note') or data.get('notes') or '').strip()
    if not closure_note:
        return jsonify({'error': 'closure_note is required to close a callback'}), 400

    complete_callback_record(cb, user, closure_note)
    db.session.commit()
    log_activity(
        user.id, 'complete_callback', 'leads', cb.lead_id, 'Lead',
        description='Marked callback as completed with closure note',
    )
    return jsonify({'callback': cb.to_dict()}), 200


@leads_bp.route('/callbacks/<int:callback_id>', methods=['PUT'])
@require_auth
def update_callback(callback_id):
    user = request.current_user
    cb = CallbackReminder.query.get(callback_id)
    if not cb or cb.tenant_id != user.tenant_id:
        return jsonify({'error': 'Callback not found'}), 404

    lead = Lead.query.get(cb.lead_id) if cb.lead_id else None
    if lead:
        err = _check_lead_access(user, lead)
        if err:
            return err

    if cb.status != 'pending':
        return jsonify({'error': 'Only pending callbacks can be edited'}), 400

    data = request.get_json() or {}
    raw_dt = (data.get('callback_datetime') or '').strip()
    if not raw_dt:
        return jsonify({'error': 'callback_datetime is required'}), 400

    try:
        old_dt, cb_dt = reschedule_callback(
            cb,
            user,
            raw_dt,
            notes_marker=data.get('notes') if 'notes' in data else None,
        )
    except ValueError as exc:
        message = str(exc) or 'Invalid datetime format. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS)'
        if 'future' in message.lower():
            return jsonify({'error': message}), 400
        return jsonify({'error': 'Invalid datetime format. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS)'}), 400
    db.session.commit()

    log_activity(
        user.id,
        'update_callback',
        'leads',
        cb.lead_id,
        'Lead',
        old_value={'callback_datetime': old_dt.isoformat() if old_dt else None},
        new_value={'callback_datetime': cb_dt.isoformat()},
        description='Updated callback schedule',
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

    # Pending callbacks cannot be hard-deleted. They must be closed with a note.
    if cb.status == 'pending':
        data = request.get_json(silent=True) or {}
        closure_note = (data.get('closure_note') or data.get('notes') or '').strip()
        if not closure_note:
            return jsonify({'error': 'closure_note is required to cancel a pending callback'}), 400

        cancel_callback_record(cb, user, closure_note)
        db.session.commit()
        log_activity(
            user.id, 'cancel_callback', 'leads', cb.lead_id, 'Lead',
            description='Cancelled callback with closure note',
        )
        return jsonify({'callback': cb.to_dict(), 'message': 'Callback cancelled'}), 200

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
