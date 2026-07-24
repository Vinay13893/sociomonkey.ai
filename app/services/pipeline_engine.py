"""Authoritative Lead lifecycle orchestration."""

from datetime import datetime
from uuid import uuid4

from app.models.action_item import ActionItem, ActionTypeConfiguration
from app.models.activity import ActivityLog
from app.models.business_configuration import LeadStatusConfiguration
from app.models.lead import Lead, StatusHistory
from app.models.notification import Notification
from app.models.pipeline import PipelineTransition
from app.models.push import NotificationEvent
from app.models.visit import Visit
from app.services.action_item_events import notify_action_item
from app.services.business_configuration import (
    evaluate_rules, status_configurations,
)
from app.utils.leads import STATUS_LABELS, VALID_STATUSES

from app.models.base import db


class PipelineTransitionError(ValueError):
    def __init__(self, message, code='INVALID_TRANSITION', details=None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _dict(row):
    return row.to_dict() if hasattr(row, 'to_dict') else dict(row)


def stage_definitions(tenant_id, include_inactive=True):
    rows = [_dict(row) for row in status_configurations(tenant_id)]
    if not include_inactive:
        rows = [
            row for row in rows
            if row.get('is_active') and row.get('visibility') == 'VISIBLE'
        ]
    return sorted(rows, key=lambda row: (row['display_order'], row['internal_key']))


def stage_definition(tenant_id, key):
    return next(
        (row for row in stage_definitions(tenant_id) if row['internal_key'] == key),
        None,
    )


def _completed_action_types(lead):
    rows = ActionItem.query.filter(
        ActionItem.tenant_id == lead.tenant_id,
        ActionItem.source_type == 'LEAD',
        ActionItem.source_id == lead.id,
        ActionItem.status_key == 'COMPLETED',
        ActionItem.is_active == True,  # noqa: E712
    ).with_entities(ActionItem.action_type_key).all()
    return {row[0] for row in rows}


def _latest_transition(lead):
    return (
        PipelineTransition.query
        .filter_by(tenant_id=lead.tenant_id, lead_id=lead.id)
        .order_by(PipelineTransition.created_at.desc(), PipelineTransition.id.desc())
        .first()
    )


def build_rule_context(lead, context=None, manager_override=False, visit=None):
    latest = _latest_transition(lead)
    stage_started = latest.created_at if latest else lead.created_at
    elapsed = (
        max(0, (datetime.utcnow() - stage_started).total_seconds() / 60)
        if stage_started else 0
    )
    completed = _completed_action_types(lead)
    supplied = context or {}
    return {
        'status': lead.status,
        'from_stage_key': lead.status,
        'manager_override': bool(manager_override),
        'time_in_stage_minutes': elapsed,
        'follow_up_completed': 'FOLLOW_UP' in completed,
        'document_collected': 'DOCUMENT_COLLECTION' in completed,
        'approval_received': 'APPROVAL' in completed,
        'completed_action_type_keys': sorted(completed),
        'visit_id': visit.id if visit else None,
        'visit_status': visit.status_key if visit else None,
        'visit_type': visit.visit_type_key if visit else None,
        **{
            key: supplied.get(key)
            for key in (
                'follow_up_completed', 'document_collected',
                'approval_received', 'time_in_stage_minutes',
            )
            if key in supplied
        },
    }


def validate_transition(
    lead, to_stage_key, context=None, manager_override=False, visit=None,
):
    current = stage_definition(lead.tenant_id, lead.status)
    target = stage_definition(lead.tenant_id, to_stage_key)
    if not target or to_stage_key not in VALID_STATUSES:
        raise PipelineTransitionError(
            'Unknown immutable pipeline stage key', 'UNKNOWN_STAGE'
        )
    if not target.get('is_active') or target.get('visibility') != 'VISIBLE':
        raise PipelineTransitionError(
            'Target pipeline stage is inactive or hidden', 'INACTIVE_STAGE'
        )
    if visit and (
        visit.tenant_id != lead.tenant_id
        or (visit.lead_id is not None and visit.lead_id != lead.id)
    ):
        raise PipelineTransitionError(
            'Visit does not belong to this Lead and tenant', 'INVALID_VISIT'
        )
    rule_context = build_rule_context(
        lead, context=context, manager_override=manager_override, visit=visit,
    )
    if manager_override:
        evaluation = {
            'passed': True,
            'manager_override': True,
            'exit': {'passed': True, 'results': []},
            'entry': {'passed': True, 'results': []},
            'required_actions': {'passed': True, 'missing': []},
        }
        return evaluation, rule_context
    exit_result = evaluate_rules(
        lead.tenant_id, (current or {}).get('exit_rule_keys') or [], rule_context
    )
    entry_context = {**rule_context, 'to_stage_key': to_stage_key}
    entry_result = evaluate_rules(
        lead.tenant_id, target.get('entry_rule_keys') or [], entry_context
    )
    required = set((current or {}).get('required_action_type_keys') or [])
    missing = sorted(required - set(rule_context['completed_action_type_keys']))
    action_result = {'passed': not missing, 'missing': missing}
    evaluation = {
        'passed': exit_result['passed'] and entry_result['passed'] and not missing,
        'manager_override': False,
        'exit': exit_result,
        'entry': entry_result,
        'required_actions': action_result,
    }
    if not evaluation['passed']:
        raise PipelineTransitionError(
            'Configured pipeline requirements are not satisfied',
            'RULES_NOT_SATISFIED',
            evaluation,
        )
    return evaluation, rule_context


def _create_default_actions(lead, stage, actor, transition):
    if not actor:
        return []
    created = []
    for index, definition in enumerate(stage.get('default_actions') or []):
        action_type = str(definition.get('action_type_key') or '').upper()
        if not action_type:
            continue
        exists = ActionTypeConfiguration.query.filter_by(
            tenant_id=lead.tenant_id,
            internal_key=action_type,
            is_active=True,
        ).first()
        if not exists:
            continue
        idempotency_key = (
            f'pipeline:{transition.id}:stage:{transition.to_stage_key}:'
            f'action:{action_type}:{index}'
        )
        row = ActionItem.query.filter_by(
            tenant_id=lead.tenant_id, idempotency_key=idempotency_key
        ).first()
        if row:
            created.append(row)
            continue
        row = ActionItem(
            tenant_id=lead.tenant_id,
            source_type='LEAD',
            source_id=lead.id,
            action_type_key=action_type,
            status_key='PENDING',
            priority_key=str(definition.get('priority_key') or 'NORMAL').upper(),
            title=str(
                definition.get('title')
                or f'{exists.display_name}: {lead.name}'
            )[:240],
            description=definition.get('description'),
            assigned_user_id=lead.assigned_to or actor.id,
            assigned_by_user_id=actor.id,
            project_id=lead.project_id,
            idempotency_key=idempotency_key,
            assigned_at=datetime.utcnow(),
            created_by=actor.id,
            updated_by=actor.id,
        )
        db.session.add(row)
        db.session.flush()
        if row.assigned_user_id and row.assigned_user:
            notify_action_item(
                row, row.assigned_user, 'assigned',
                correlation_id=transition.correlation_id,
                idempotency_key=f'{idempotency_key}:notification',
            )
        created.append(row)
    return created


def _notify_transition(lead, actor, transition, from_label, to_label):
    user = lead.assigned_user
    if not user or (actor and user.id == actor.id):
        return None
    title = 'Lead Pipeline Updated'
    message = f'{lead.name} moved from {from_label} to {to_label}.'
    tenant = getattr(user, 'tenant', None)
    slug = getattr(tenant, 'slug', None) or ''
    payload = {
        'lead_id': lead.id,
        'pipeline_transition_id': transition.id,
        'from_stage_key': transition.from_stage_key,
        'to_stage_key': transition.to_stage_key,
        'correlation_id': transition.correlation_id,
    }
    db.session.add(Notification(
        tenant_id=lead.tenant_id,
        user_id=user.id,
        category='pipeline',
        kind='pipeline_stage_changed',
        title=title,
        message=message,
        payload=payload,
        source='pipeline',
    ))
    event = NotificationEvent(
        tenant_id=lead.tenant_id,
        correlation_id=transition.correlation_id,
        idempotency_key=f'pipeline-transition:{transition.id}:user:{user.id}',
        user_id=user.id,
        event_type='pipeline_stage_changed',
        lead_id=lead.id,
        pipeline_transition_id=transition.id,
        title=title,
        body=message,
        deep_link=f'/{slug}/leads?lead={lead.id}' if slug else '/',
        payload=payload,
        status='queued',
    )
    db.session.add(event)
    return event


def transition_lead(
    lead, to_stage_key, actor=None, source='PIPELINE', reason=None,
    context=None, manager_override=False, visit=None, channel_partner_id=None,
    correlation_id=None, notify=True,
):
    """Move a Lead and append every audit artifact in the current transaction."""
    if not lead or not lead.is_active:
        raise PipelineTransitionError('Lead is inactive or missing', 'LEAD_NOT_FOUND')
    if actor and actor.tenant_id != lead.tenant_id:
        raise PipelineTransitionError('Cross-tenant transition denied', 'TENANT_MISMATCH')
    if lead.status == to_stage_key:
        return None, []
    evaluation, rule_context = validate_transition(
        lead, to_stage_key, context=context,
        manager_override=manager_override, visit=visit,
    )
    old_status = lead.status
    cid = str(correlation_id or uuid4())[:36]
    lead.status = to_stage_key
    db.session.add(StatusHistory(
        lead_id=lead.id,
        old_status=old_status,
        new_status=to_stage_key,
        changed_by=actor.id if actor else None,
    ))
    transition = PipelineTransition(
        tenant_id=lead.tenant_id,
        lead_id=lead.id,
        from_stage_key=old_status,
        to_stage_key=to_stage_key,
        changed_by_user_id=actor.id if actor else None,
        source=str(source or 'PIPELINE').upper()[:80],
        reason=(reason or '').strip() or None,
        correlation_id=cid,
        rule_evaluation=evaluation,
        transition_context={
            'visit_status': rule_context.get('visit_status'),
            'completed_action_type_keys': rule_context.get(
                'completed_action_type_keys', []
            ),
            'time_in_stage_minutes': rule_context.get('time_in_stage_minutes'),
        },
        previous_owner_id=lead.assigned_to,
        current_owner_id=lead.assigned_to,
        manager_override=bool(manager_override),
        visit_id=visit.id if visit else None,
        channel_partner_id=channel_partner_id or lead.channel_partner_id,
    )
    db.session.add(transition)
    db.session.flush()
    from_label = STATUS_LABELS.get(
        old_status, str(old_status or '').replace('_', ' ').title()
    )
    target = stage_definition(lead.tenant_id, to_stage_key) or {}
    to_label = target.get('display_name') or STATUS_LABELS.get(
        to_stage_key, to_stage_key.replace('_', ' ').title()
    )
    db.session.add(ActivityLog(
        tenant_id=lead.tenant_id,
        user_id=actor.id if actor else None,
        action='pipeline_stage_transition',
        module='pipeline',
        resource_id=lead.id,
        resource_type='Lead',
        old_value={'status': old_status, 'status_label': from_label},
        new_value={
            'status': to_stage_key,
            'status_label': to_label,
            'source': transition.source,
            'manager_override': transition.manager_override,
            'visit_id': transition.visit_id,
        },
        description=f'Lead moved from {from_label} to {to_label}',
        correlation_id=cid,
    ))
    actions = _create_default_actions(lead, target, actor, transition)
    if notify:
        _notify_transition(lead, actor, transition, from_label, to_label)
    return transition, actions


def record_initial_stage(lead, source='INGESTION', correlation_id=None):
    """Append an initial event for a newly created Lead without rewriting history."""
    transition = PipelineTransition(
        tenant_id=lead.tenant_id,
        lead_id=lead.id,
        from_stage_key=None,
        to_stage_key=lead.status or 'new',
        source=str(source or 'INGESTION').upper()[:80],
        correlation_id=str(correlation_id or uuid4())[:36],
        rule_evaluation={'passed': True, 'initial': True},
        transition_context={},
        current_owner_id=lead.assigned_to,
    )
    db.session.add(transition)
    return transition
