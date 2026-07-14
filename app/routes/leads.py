from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta, timezone

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
from app.utils.leads import get_user_visible_leads, apply_test_lead_filter, VALID_STATUSES
from app.utils.lead_source_cutoff import lead_source_cutoff_for
from app.utils.time_utils import to_ist_str
from app.services.reminder_scheduler import push_notification

leads_bp = Blueprint('leads', __name__, url_prefix='/api/leads')

CALL_OUTCOME_LABELS = {
    'connected': 'Connected',
    'no_answer': 'No Answer',
    'busy': 'Busy',
    'wrong_number': 'Wrong Number',
    'callback_scheduled': 'Callback Scheduled',
}

IST = timezone(timedelta(hours=5, minutes=30))


def _parse_ist_datetime(raw_value):
    if not raw_value:
        raise ValueError('Missing datetime value')
    parsed = datetime.fromisoformat(str(raw_value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    else:
        parsed = parsed.astimezone(IST)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


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

        if lead.status in ['lost', 'junk']:
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
            lead_id=lead_id,
            assigned_from=old_assignee_id,
            assigned_to=new_assignee.id,
            assigned_by=user.id,
            reason=reason,
        ))
        lead.assigned_to = new_assignee.id
        lead.assigned_by = user.id
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
    tenant_cutoff = lead_source_cutoff_for(user, tenant_id=user.tenant_id)
    if tenant_cutoff:
        source_lead_ids = (
            db.session.query(IngestedLeadLog.lead_id)
            .join(LeadSource, IngestedLeadLog.source_id == LeadSource.id)
            .filter(IngestedLeadLog.tenant_id == user.tenant_id)
            .filter(LeadSource.tenant_id == user.tenant_id)
            .filter(LeadSource.is_active == True)
            .filter(IngestedLeadLog.status == 'processed')
            .filter(IngestedLeadLog.lead_id.isnot(None))
            .filter(IngestedLeadLog.received_at >= tenant_cutoff)
            .distinct()
            .subquery()
        )
        # Keep manual/sheet-imported leads visible while gating ingestion leads by cutoff.
        query = query.filter((Lead.created_by.isnot(None)) | (Lead.id.in_(source_lead_ids)))
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
            query = query.filter(Lead.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            return jsonify({'error': 'date_from must be YYYY-MM-DD'}), 400
    if date_to:
        try:
            query = query.filter(Lead.created_at < (datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)))
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
        phone=phone_val or None,
        alternate_phone=alternate_phone_val or None,
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
            from app.services.notification_processor import process_notification_queue
            assigned_user = User.query.get(lead.assigned_to)
            if assigned_user:
                enqueue_lead_assigned(assigned_user, lead)
                db.session.commit()
                process_notification_queue(batch_size=50)
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
        lead.status = new_status
        db.session.add(StatusHistory(
            lead_id=lead_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=user.id,
        ))

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
            })
            try:
                from app.services.notification_events import enqueue_lead_assigned
                from app.services.notification_processor import process_notification_queue
                # Enqueue one event summarising the bulk assignment (first lead as anchor)
                first_lead_id = lead_ids[0] if lead_ids else None
                first_lead = Lead.query.get(first_lead_id) if first_lead_id else None
                if first_lead:
                    ev = enqueue_lead_assigned(target, first_lead)
                    # Override title/body for bulk context
                    ev.title = 'New Leads Assigned'
                    ev.body = f'{updated} new lead{"s" if updated != 1 else ""} assigned to you'
                    db.session.commit()
                    process_notification_queue(batch_size=50)
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
        })
        try:
            from app.services.notification_events import enqueue_lead_reassigned
            from app.services.notification_processor import process_notification_queue
            enqueue_lead_reassigned(target, lead)
            db.session.commit()
            process_notification_queue(batch_size=50)
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
        return apply_project_filter(apply_time_filter(q))

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

    visible = get_user_visible_leads(viewing_user)

    if range_requested:
        lead_scope = visible.filter(
            db.or_(
                db.and_(Lead.created_at >= range_start, Lead.created_at < range_end),
                db.and_(Lead.updated_at >= range_start, Lead.updated_at < range_end),
            )
        )
    else:
        lead_scope = visible

    visible_ids_subq = visible.with_entities(Lead.id.label('id')).subquery()

    # ── Callback queries (scoped by role) ────────────────────────────────────
    cb_base = CallbackReminder.query.filter(
        CallbackReminder.tenant_id == viewing_user.tenant_id,
        CallbackReminder.status == 'pending',
    )
    if viewing_user.role == 'team_member':
        cb_base = cb_base.filter(CallbackReminder.assigned_user_id == viewing_user.id)
    elif viewing_user.role == 'sales_manager':
        team_ids = [u.id for u in User.query.filter_by(manager_id=viewing_user.id).all()]
        team_ids.append(viewing_user.id)
        cb_base = cb_base.filter(
            db.or_(
                CallbackReminder.assigned_user_id.in_(team_ids),
                CallbackReminder.manager_id == viewing_user.id,
            )
        )

    # Keep callbacks in the same visibility boundary as lead lists.
    # Use a subquery instead of materializing lead IDs in Python to avoid
    # large IN lists and expensive memory usage on tenants with many leads.
    cb_base = cb_base.filter(
        CallbackReminder.lead_id.in_(db.select(visible_ids_subq.c.id))
    )

    # Prevent N+1 query explosions while serializing callback rows.
    cb_base = cb_base.options(
        joinedload(CallbackReminder.lead).joinedload(Lead.project),
        joinedload(CallbackReminder.lead).selectinload(Lead.notes),
    )

    callback_window_start = range_start if range_requested else today_start
    callback_window_end   = range_end if range_requested else today_end

    # FIFO per lead for callbacks: if multiple pending callbacks exist for the
    # same lead, keep the first input (oldest created callback record).
    all_pending_callbacks = cb_base.order_by(
        CallbackReminder.created_at.asc(),
        CallbackReminder.id.asc(),
    ).all()

    first_callback_by_lead = {}
    passthrough_callbacks = []
    for cb in all_pending_callbacks:
        # Safety: callbacks without lead_id are kept as-is.
        if not cb.lead_id:
            passthrough_callbacks.append(cb)
            continue
        if cb.lead_id not in first_callback_by_lead:
            first_callback_by_lead[cb.lead_id] = cb

    unique_callbacks = list(first_callback_by_lead.values()) + passthrough_callbacks

    current_callbacks = [
        cb for cb in unique_callbacks
        if cb.callback_datetime >= callback_window_start and cb.callback_datetime < callback_window_end
    ]
    overdue_callbacks = [
        cb for cb in unique_callbacks
        if cb.callback_datetime < callback_window_start
    ]

    # Keep display order by due time inside each section.
    current_callbacks.sort(key=lambda cb: cb.callback_datetime)
    overdue_callbacks.sort(key=lambda cb: cb.callback_datetime)

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
        d['lead_created_at'] = lead.created_at.isoformat() if lead and lead.created_at else None
        d['project_name'] = lead.project.name if lead and lead.project else None
        d['project_id'] = lead.project_id if lead else None
        if lead and lead.notes:
            latest_note = sorted(lead.notes, key=lambda n: n.created_at or datetime.min, reverse=True)[0]
            d['latest_note'] = latest_note.note if latest_note else None
        else:
            d['latest_note'] = None
        return d

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

    overdue_callback_lead_ids = list({c.lead_id for c in overdue_callbacks if c.lead_id})
    callback_lead_ids = {c.lead_id for c in current_callbacks if c.lead_id}
    callback_lead_ids.update(overdue_callback_lead_ids)

    lead_buckets_base = visible
    if callback_lead_ids:
        lead_buckets_base = lead_buckets_base.filter(~Lead.id.in_(list(callback_lead_ids)))

    # New leads should always surface in Action Board within the selected window.
    new_bucket_q = lead_buckets_base.filter(Lead.status == 'new')

    follow_up_q = lead_buckets_base.filter(Lead.status == 'follow_up')
    no_answer_q = lead_buckets_base.filter(Lead.status == 'no_answer')
    warm_q = lead_buckets_base.filter(Lead.status.in_(warm_statuses))
    hot_q = lead_buckets_base.filter(Lead.status.in_(hot_statuses))

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
# Assign / Reassign
# ---------------------------------------------------------------------------

ALL_LEAD_STATUSES = [
    'new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
    'site_visit_planned', 'site_visit_done', 'negotiation', 'booking_done',
    'not_interested', 'lost', 'junk',
]


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
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(500, max(10, int(request.args.get('per_page', 25))))
    total = q.count()
    leads = q.order_by(Lead.created_at.asc()).offset((page - 1) * per_page).limit(per_page).all()
    assignable = _assignable_users(user)
    return jsonify({
        'leads': [l.to_dict() for l in leads],
        'total': total,
        'page': page,
        'per_page': per_page,
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

    page = max(1, int(request.args.get('page', 1)))
    per_page = min(500, max(10, int(request.args.get('per_page', 25))))
    total = q.count()
    leads = q.order_by(Lead.updated_at.asc()).offset((page - 1) * per_page).limit(per_page).all()
    assignable = _assignable_users(user)
    return jsonify({
        'leads': [l.to_dict() for l in leads],
        'total': total,
        'page': page,
        'per_page': per_page,
        'days': days,
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

    NON_ACTIVE = ['lost', 'junk', 'booking_done', 'not_interested']
    result = []
    for m in members:
        total = Lead.query.filter(Lead.tenant_id == user.tenant_id, Lead.is_active == True, Lead.assigned_to == m.id).count()
        active = Lead.query.filter(
            Lead.tenant_id == user.tenant_id,
            Lead.is_active == True,
            Lead.assigned_to == m.id,
            Lead.status.notin_(NON_ACTIVE),
        ).count()
        overdue_cb = db.session.query(func.count(func.distinct(CallbackReminder.lead_id))).filter(
            CallbackReminder.tenant_id == user.tenant_id,
            CallbackReminder.assigned_user_id == m.id,
            CallbackReminder.status == 'pending',
            CallbackReminder.callback_datetime < datetime.utcnow(),
        ).scalar() or 0
        result.append({
            'id': m.id, 'name': m.name, 'role': m.role,
            'total_leads': total, 'active_leads': active,
            'overdue_callbacks': overdue_cb,
        })
    result.sort(key=lambda x: x['active_leads'], reverse=True)
    assignable = _assignable_users(user)
    return jsonify({
        'members': result,
        'assignable_users': [{'id': u.id, 'name': u.name, 'role': u.role} for u in assignable],
    }), 200


@leads_bp.route('/assign-reassign/bulk-assign', methods=['POST'])
@require_role('superadmin', 'sales_manager')
def ar_bulk_assign():
    """Bulk assign or reassign leads to a target user."""
    user = request.current_user
    data = request.get_json() or {}
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

    assigned = 0
    for lid in lead_ids:
        lead = Lead.query.filter_by(id=lid, tenant_id=user.tenant_id, is_active=True).first()
        if not lead:
            continue
        # Manager scope check
        if user.role == 'sales_manager':
            allowed_lead_ids = [tm.id for tm in user.team_members] + [user.id, None]
            if lead.assigned_to not in allowed_lead_ids:
                continue
        old_assignee = lead.assigned_to
        lead.assigned_to = target.id
        db.session.add(LeadAssignmentHistory(
            lead_id=lead.id,
            assigned_from=old_assignee,
            assigned_to=target.id,
            assigned_by=user.id,
            reason=data.get('reason', 'Bulk assign/reassign'),
        ))
        log_activity(user.id, 'assign_lead', 'leads', lead.id, 'Lead',
            description=f'Bulk assigned lead {lead.name} to {target.name}')
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
        })
        try:
            from app.services.notification_events import enqueue_lead_assigned
            from app.services.notification_processor import process_notification_queue
            first_lead = Lead.query.filter_by(id=lead_ids[0], tenant_id=user.tenant_id).first() if lead_ids else None
            if first_lead:
                ev = enqueue_lead_assigned(target, first_lead)
                ev.title = 'New Leads Assigned'
                ev.body = f'{assigned} new lead{"s" if assigned != 1 else ""} assigned to you'
                db.session.commit()
                process_notification_queue(batch_size=50)
        except Exception:
            db.session.rollback()

    return jsonify({'assigned': assigned, 'total_requested': len(lead_ids)}), 200
@require_role('superadmin', 'sales_manager')
def ar_workload_move():
    """Move N active leads from one member to another."""
    user = request.current_user
    data = request.get_json() or {}
    from_id = data.get('from_user_id')
    to_id = data.get('to_user_id')
    try:
        count = max(1, min(500, int(data.get('count', 10))))
    except (TypeError, ValueError):
        count = 10

    if not from_id or not to_id:
        return jsonify({'error': 'from_user_id and to_user_id required'}), 400

    from_user = User.query.filter_by(id=int(from_id), tenant_id=user.tenant_id, is_active=True).first()
    to_user = User.query.filter_by(id=int(to_id), tenant_id=user.tenant_id, is_active=True).first()
    if not from_user or not to_user:
        return jsonify({'error': 'User not found'}), 404

    if user.role == 'sales_manager':
        allowed_ids = [tm.id for tm in user.team_members] + [user.id]
        if from_user.id not in allowed_ids or to_user.id not in allowed_ids:
            return jsonify({'error': 'Users outside your team'}), 403

    NON_ACTIVE = ['lost', 'junk', 'booking_done', 'not_interested']
    status_filter = (data.get('status_filter') or '').strip()
    leads_q = Lead.query.filter(
        Lead.tenant_id == user.tenant_id,
        Lead.is_active == True,
        Lead.assigned_to == from_user.id,
    )
    if status_filter:
        leads_q = leads_q.filter(Lead.status == status_filter)
    else:
        leads_q = leads_q.filter(Lead.status.notin_(NON_ACTIVE))
    leads = leads_q.order_by(Lead.updated_at.asc()).limit(count).all()

    moved = 0
    for lead in leads:
        lead.assigned_to = to_user.id
        db.session.add(LeadAssignmentHistory(
            lead_id=lead.id,
            assigned_from=from_user.id,
            assigned_to=to_user.id,
            assigned_by=user.id,
            reason='Workload rebalance',
        ))
        log_activity(user.id, 'assign_lead', 'leads', lead.id, 'Lead',
            description=f'Workload move: {lead.name} from {from_user.name} to {to_user.name}')
        moved += 1

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
        })
        try:
            from app.services.notification_events import enqueue_lead_assigned
            from app.services.notification_processor import process_notification_queue
            if leads:
                ev = enqueue_lead_assigned(to_user, leads[0])
                ev.title = 'Leads Transferred to You'
                ev.body = f'{moved} lead{"s" if moved != 1 else ""} transferred from {from_user.name}'
                db.session.commit()
                process_notification_queue(batch_size=50)
        except Exception:
            db.session.rollback()

    return jsonify({'moved': moved}), 200
# ---------------------------------------------------------------------------

RECYCLE_STATUSES = [
    'new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
    'site_visit_planned', 'site_visit_done', 'negotiation', 'booking_done',
    'not_interested', 'lost', 'junk',
]


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
    query_text = (request.args.get('q') or '').strip().lower()
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get('page_size', 25))
    except (TypeError, ValueError):
        page_size = 25
    page_size = max(1, min(1000, page_size))
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

    if query_text:
        like_q = f'%{query_text}%'
        base = base.outerjoin(User, Lead.assigned_to == User.id).outerjoin(Project, Lead.project_id == Project.id).filter(
            db.or_(
                func.lower(Lead.name).like(like_q),
                func.lower(func.coalesce(Lead.phone, '')).like(like_q),
                func.lower(func.coalesce(Project.name, '')).like(like_q),
                func.lower(func.coalesce(User.name, '')).like(like_q),
            )
        )

    total = base.count()
    offset = (page - 1) * page_size
    leads = base.order_by(Lead.updated_at.asc()).offset(offset).limit(page_size).all()

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
        'page':       page,
        'page_size':  page_size,
        'total_pages': max(1, (total + page_size - 1) // page_size),
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
    if len(lead_ids) > 500:
        return jsonify({'error': 'Max 500 leads per reshuffle'}), 400

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
        return jsonify({'job': job.to_dict(), 'status': 'queued'}), 202

    # Gather eligible team members
    if user.role == 'sales_manager':
        team = User.query.filter_by(manager_id=user.id, is_active=True).all()
    else:  # superadmin
        team = User.query.filter_by(role='team_member', tenant_id=user.tenant_id, is_active=True).all()

    if not team:
        return jsonify({'error': 'No active team members available'}), 400

    result = _process_reshuffle_job(job, user, team, strategy, reason, cooldown_days)
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

    return jsonify({
        'lead': lead.to_dict(),
        'acquisition': acquisition,
        'notes': [n.to_dict() for n in notes],
        'status_history': [h.to_dict() for h in status_history],
        'assignment_history': [h.to_dict() for h in assignment_history],
        'callbacks': [c.to_dict() for c in callbacks],
        'call_activities': [log.to_dict() for log in call_logs],
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
        cb_dt = _parse_ist_datetime(raw_dt)
    except ValueError:
        return jsonify({'error': 'Invalid datetime format. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS)'}), 400

    if cb_dt <= datetime.utcnow():
        return jsonify({'error': 'Callback time must be in the future'}), 400

    # Only one pending callback per lead is allowed.
    existing_pending = (
        CallbackReminder.query
        .filter_by(lead_id=lead_id, status='pending')
        .order_by(CallbackReminder.created_at.asc(), CallbackReminder.id.asc())
        .first()
    )
    if existing_pending:
        return jsonify({
            'error': 'A pending callback already exists for this lead. Close it with a note before creating a new one.',
            'pending_callback': existing_pending.to_dict(),
        }), 409

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

    # Auto-update lead status to callback_scheduled
    old_status = lead.status
    if old_status != 'callback_scheduled':
        lead.status = 'callback_scheduled'
        db.session.add(StatusHistory(
            lead_id=lead_id,
            old_status=old_status,
            new_status='callback_scheduled',
            changed_by=user.id,
        ))

    db.session.commit()

    log_activity(
        user.id, 'create_callback', 'leads', lead_id, 'Lead',
        description=f'Scheduled callback for lead {lead.name} at {_format_ist_datetime(cb_dt)}',
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

    from app.utils.time_utils import now_ist
    closed_at = now_ist().strftime('%d %b %Y %H:%M IST')
    actor = user.name or user.email or f'User {user.id}'
    closure_entry = f'[COMPLETED by {actor} at {closed_at}] {closure_note}'
    cb.notes = f'{cb.notes}\n{closure_entry}'.strip() if cb.notes else closure_entry

    cb.status = 'completed'
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
        cb_dt = _parse_ist_datetime(raw_dt)
    except ValueError:
        return jsonify({'error': 'Invalid datetime format. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS)'}), 400

    if cb_dt <= datetime.utcnow():
        return jsonify({'error': 'Callback time must be in the future'}), 400

    old_dt = cb.callback_datetime
    cb.callback_datetime = cb_dt
    if 'notes' in data:
        cb.notes = (data.get('notes') or '').strip() or None
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

        from app.utils.time_utils import now_ist
        closed_at = now_ist().strftime('%d %b %Y %H:%M IST')
        actor = user.name or user.email or f'User {user.id}'
        closure_entry = f'[CANCELLED by {actor} at {closed_at}] {closure_note}'
        cb.notes = f'{cb.notes}\n{closure_entry}'.strip() if cb.notes else closure_entry
        cb.status = 'cancelled'
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
