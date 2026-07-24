"""Unified, capability-scoped Lead Pipeline APIs."""

from datetime import datetime, timedelta
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import case, func, or_

from app.middleware import require_capability
from app.models.action_item import ActionItem
from app.models.activity import ActivityLog
from app.models.base import db
from app.models.channel_partner import ChannelPartner
from app.models.lead import Lead, LeadAssignmentHistory
from app.models.pipeline import PipelineTransition
from app.models.user import User
from app.models.visit import Visit
from app.services.permissions import capability_decision
from app.services.pipeline_engine import (
    PipelineTransitionError, stage_definitions, transition_lead,
)
from app.utils.leads import get_user_visible_leads
from app.utils.time_utils import business_date_bounds_utc_naive


pipeline_bp = Blueprint('pipeline', __name__, url_prefix='/api/pipeline')


def _tenant_id():
    return request.current_user.tenant_id or getattr(
        request, 'current_tenant_id', None
    )


def _cid():
    return str(request.headers.get('X-Correlation-ID') or uuid4())[:36]


def _visible_query():
    return get_user_visible_leads(request.current_user).filter(
        Lead.tenant_id == _tenant_id(),
        Lead.is_active == True,  # noqa: E712
    )


def _filtered_query():
    query = _visible_query()
    stage = (request.args.get('stage') or '').strip()
    project_id = request.args.get('project_id', type=int)
    manager_id = request.args.get('manager_id', type=int)
    owner_id = request.args.get('owner_id', type=int)
    search = (request.args.get('search') or '').strip()
    if stage:
        query = query.filter(Lead.status == stage)
    if project_id:
        query = query.filter(Lead.project_id == project_id)
    if owner_id:
        query = query.filter(Lead.assigned_to == owner_id)
    if manager_id:
        team_ids = [
            row[0] for row in User.query.filter_by(
                tenant_id=_tenant_id(), manager_id=manager_id, is_active=True
            ).with_entities(User.id).all()
        ]
        query = query.filter(or_(
            Lead.sales_manager_id == manager_id,
            Lead.assigned_to.in_([manager_id, *team_ids]),
        ))
    if search:
        term = f'%{search}%'
        query = query.filter(or_(
            Lead.name.ilike(term), Lead.phone.ilike(term),
            Lead.email.ilike(term),
        ))
    return query


@pipeline_bp.get('/stages')
@require_capability('pipeline.view', 'OWN')
def get_pipeline_stages():
    page = max(1, request.args.get('page', 1, type=int))
    per_stage = min(50, max(1, request.args.get('per_stage', 10, type=int)))
    stages = stage_definitions(_tenant_id(), include_inactive=True)
    base = _filtered_query()
    counts = dict(
        base.with_entities(Lead.status, func.count(Lead.id))
        .group_by(Lead.status).all()
    )
    pipeline = {}
    for stage in stages:
        key = stage['internal_key']
        leads = (
            base.filter(Lead.status == key)
            .order_by(Lead.updated_at.desc(), Lead.id.desc())
            .offset((page - 1) * per_stage)
            .limit(per_stage)
            .all()
        )
        pipeline[key] = {
            'count': int(counts.get(key, 0)),
            'leads': [lead.to_dict() for lead in leads],
            'page': page,
            'per_stage': per_stage,
        }
    return jsonify({'stages': stages, 'pipeline': pipeline}), 200


@pipeline_bp.get('/stages/<string:stage_key>/leads')
@require_capability('pipeline.view', 'OWN')
def pipeline_stage_leads(stage_key):
    valid_keys = {
        row['internal_key'] for row in stage_definitions(_tenant_id())
    }
    if stage_key not in valid_keys:
        return jsonify({'error': 'Unknown pipeline stage'}), 404
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(50, max(1, request.args.get('per_page', 10, type=int)))
    query = _filtered_query().filter(Lead.status == stage_key)
    total = query.count()
    rows = (
        query.order_by(Lead.updated_at.desc(), Lead.id.desc())
        .offset((page - 1) * per_page).limit(per_page).all()
    )
    return jsonify({
        'stage_key': stage_key,
        'leads': [row.to_dict() for row in rows],
        'pagination': {
            'page': page, 'per_page': per_page, 'total': total,
            'pages': max(1, (total + per_page - 1) // per_page),
        },
    })


@pipeline_bp.get('/dashboard')
@require_capability('pipeline.view', 'OWN')
def pipeline_dashboard():
    query = _filtered_query()
    stages = stage_definitions(_tenant_id(), include_inactive=True)
    counts = dict(
        query.with_entities(Lead.status, func.count(Lead.id))
        .group_by(Lead.status).all()
    )
    total = sum(counts.values())
    stale_hours = min(24 * 90, max(1, request.args.get(
        'stalled_hours', 72, type=int
    )))
    stalled_cutoff = datetime.utcnow() - timedelta(hours=stale_hours)
    stalled = query.filter(Lead.updated_at <= stalled_cutoff).count()
    start, end = business_date_bounds_utc_naive()
    visible_ids = query.with_entities(Lead.id).subquery()
    today_movements = PipelineTransition.query.filter(
        PipelineTransition.tenant_id == _tenant_id(),
        PipelineTransition.lead_id.in_(db.session.query(visible_ids.c.id)),
        PipelineTransition.created_at >= start,
        PipelineTransition.created_at < end,
    ).count()
    manager_escalations = ActionItem.query.filter(
        ActionItem.tenant_id == _tenant_id(),
        ActionItem.source_type == 'LEAD',
        ActionItem.source_id.in_(db.session.query(visible_ids.c.id)),
        ActionItem.priority_key.in_(['HIGH', 'URGENT']),
        ActionItem.status_key.notin_(['COMPLETED', 'CANCELLED', 'EXPIRED']),
        ActionItem.is_active == True,  # noqa: E712
    ).count()
    high_priority = (
        ActionItem.query.filter(
            ActionItem.tenant_id == _tenant_id(),
            ActionItem.source_type == 'LEAD',
            ActionItem.source_id.in_(db.session.query(visible_ids.c.id)),
            ActionItem.priority_key.in_(['HIGH', 'URGENT']),
            ActionItem.status_key.notin_(['COMPLETED', 'CANCELLED', 'EXPIRED']),
            ActionItem.is_active == True,  # noqa: E712
        )
        .order_by(ActionItem.due_at.asc(), ActionItem.id.asc())
        .limit(20).all()
    )
    latest_stage = (
        db.session.query(
            PipelineTransition.lead_id,
            func.max(PipelineTransition.created_at).label('stage_started_at'),
        )
        .filter(PipelineTransition.tenant_id == _tenant_id())
        .group_by(PipelineTransition.lead_id)
        .subquery()
    )
    now = datetime.utcnow()
    stage_started_at = func.coalesce(
        latest_stage.c.stage_started_at, Lead.created_at
    )
    ageing_bucket = case(
        (stage_started_at >= now - timedelta(days=1), 'under_1_day'),
        (stage_started_at >= now - timedelta(days=3), 'one_to_3_days'),
        (stage_started_at >= now - timedelta(days=7), 'three_to_7_days'),
        else_='over_7_days',
    )
    ageing_rows = (
        query.outerjoin(latest_stage, latest_stage.c.lead_id == Lead.id)
        .with_entities(
            Lead.status,
            ageing_bucket.label('ageing_bucket'),
            func.count(Lead.id),
        )
        .group_by(Lead.status, ageing_bucket)
        .all()
    )
    ageing_by_stage = {}
    for status_key, bucket, count in ageing_rows:
        ageing_by_stage.setdefault(status_key, {
            'under_1_day': 0,
            'one_to_3_days': 0,
            'three_to_7_days': 0,
            'over_7_days': 0,
        })[bucket] = int(count)
    stage_items = [
        {
            **stage,
            'count': int(counts.get(stage['internal_key'], 0)),
            'percentage': round(
                (counts.get(stage['internal_key'], 0) / total * 100), 2
            ) if total else 0,
        }
        for stage in stages
    ]
    return jsonify({
        'total_leads': total,
        'leads_by_stage': stage_items,
        'conversion_funnel': stage_items,
        'stage_ageing': [
            {
                'internal_key': stage['internal_key'],
                'display_name': stage['display_name'],
                'buckets': ageing_by_stage.get(stage['internal_key'], {
                    'under_1_day': 0,
                    'one_to_3_days': 0,
                    'three_to_7_days': 0,
                    'over_7_days': 0,
                }),
            }
            for stage in stages
        ],
        'stalled_leads': stalled,
        'stalled_hours': stale_hours,
        'todays_movements': today_movements,
        'manager_escalations': manager_escalations,
        'high_priority_pipeline': [
            {
                'action_item_id': row.id,
                'lead_id': row.source_id,
                'title': row.title,
                'priority_key': row.priority_key,
                'due_at': row.to_dict()['due_at'],
            }
            for row in high_priority
        ],
    })


@pipeline_bp.post('/leads/<int:lead_id>/move')
@require_capability('pipeline.move', 'OWN')
def move_pipeline_lead(lead_id):
    user = request.current_user
    data = request.get_json() or {}
    lead = _visible_query().filter(Lead.id == lead_id).first()
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    manager_override = bool(data.get('manager_override', False))
    if manager_override and not capability_decision(
        user, 'pipeline.override', 'TEAM'
    )['allowed']:
        return jsonify({'error': 'Manager override permission required'}), 403
    visit = None
    if data.get('visit_id') is not None:
        visit = Visit.query.filter_by(
            id=data['visit_id'], tenant_id=_tenant_id(), is_active=True
        ).first()
        if not visit:
            return jsonify({'error': 'Visit not found in tenant'}), 400
    channel_partner_id = data.get('channel_partner_id')
    if channel_partner_id is not None and not ChannelPartner.query.filter_by(
        id=channel_partner_id, tenant_id=_tenant_id(), is_active=True
    ).first():
        return jsonify({'error': 'Channel Partner not found in tenant'}), 400
    try:
        transition, actions = transition_lead(
            lead,
            str(data.get('to_status') or '').strip(),
            actor=user,
            source=data.get('source') or 'PIPELINE',
            reason=data.get('reason'),
            context=data.get('context') if isinstance(data.get('context'), dict) else {},
            manager_override=manager_override,
            visit=visit,
            channel_partner_id=channel_partner_id,
            correlation_id=_cid(),
        )
        if not transition:
            return jsonify({
                'lead': lead.to_dict(),
                'message': 'No status change required',
            }), 200
        db.session.commit()
    except PipelineTransitionError as exc:
        db.session.rollback()
        return jsonify({
            'error': str(exc), 'code': exc.code, 'details': exc.details,
        }), 409 if exc.code == 'RULES_NOT_SATISFIED' else 400
    return jsonify({
        'lead': lead.to_dict(),
        'transition': transition.to_dict(),
        'generated_action_items': [row.to_dict() for row in actions],
    }), 200


@pipeline_bp.get('/leads/<int:lead_id>/history')
@require_capability('pipeline.view', 'OWN')
def pipeline_history(lead_id):
    if not _visible_query().filter(Lead.id == lead_id).first():
        return jsonify({'error': 'Lead not found'}), 404
    rows = (
        PipelineTransition.query
        .filter_by(tenant_id=_tenant_id(), lead_id=lead_id)
        .order_by(PipelineTransition.created_at.desc(), PipelineTransition.id.desc())
        .limit(500).all()
    )
    return jsonify({'history': [row.to_dict() for row in rows]})


@pipeline_bp.post('/leads/<int:lead_id>/assign')
@require_capability('pipeline.assign', 'TEAM')
def assign_pipeline_owner(lead_id):
    user = request.current_user
    data = request.get_json() or {}
    lead = _visible_query().filter(Lead.id == lead_id).first()
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    target = User.query.filter_by(
        id=data.get('assigned_to'), tenant_id=_tenant_id(), is_active=True
    ).first()
    if not target:
        return jsonify({'error': 'Target user not found in tenant'}), 400
    override = bool(data.get('manager_override'))
    if override and not capability_decision(
        user, 'pipeline.override', 'TEAM'
    )['allowed']:
        return jsonify({'error': 'Manager override permission required'}), 403
    cid = _cid()
    old_owner = lead.assigned_to
    lead.assigned_to = target.id
    lead.assigned_by = user.id
    history = LeadAssignmentHistory(
        tenant_id=_tenant_id(),
        lead_id=lead.id,
        assigned_from=old_owner,
        assigned_to=target.id,
        assigned_by=user.id,
        reason=(data.get('reason') or '').strip() or None,
        source='PIPELINE',
        correlation_id=cid,
        is_manager_override=override,
    )
    db.session.add(history)
    db.session.add(ActivityLog(
        tenant_id=_tenant_id(),
        user_id=user.id,
        action='pipeline_owner_assigned',
        module='pipeline',
        resource_id=lead.id,
        resource_type='Lead',
        old_value={'assigned_to': old_owner},
        new_value={
            'assigned_to': target.id, 'manager_override': override,
        },
        description='Pipeline Lead owner changed',
        correlation_id=cid,
    ))
    db.session.commit()
    return jsonify({
        'lead': lead.to_dict(),
        'assignment': history.to_dict(),
        'correlation_id': cid,
    })
