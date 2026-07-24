"""Backward-compatible configuration resolution and rule evaluation."""

from datetime import datetime

from app.models.business_configuration import (
    BusinessRuleConfiguration, LeadStatusConfiguration,
)
from app.utils.leads import STATUS_LABELS, VALID_STATUSES


DEFAULT_RULES = {
    'warm_lead': {'status_in': ['interested', 'site_visit_planned']},
    'hot_lead': {'status_in': ['site_visit_done', 'negotiation']},
    'cold_lead': {'status_in': ['new', 'no_answer']},
    'sla': {'minutes': 30},
    'escalation': {'overdue_minutes': 60},
    'callback_ageing': {'warning_minutes': 10},
    'priority': {'status_weights': {'hot': 100, 'warm': 50, 'cold': 10}},
    'pipeline_follow_up_completed': {
        'field': 'follow_up_completed', 'operator': 'equals', 'value': True,
    },
    'pipeline_visit_completed': {
        'field': 'visit_status', 'operator': 'in',
        'value': ['COMPLETED'],
    },
    'pipeline_document_collected': {
        'field': 'document_collected', 'operator': 'equals', 'value': True,
    },
    'pipeline_approval_received': {
        'field': 'approval_received', 'operator': 'equals', 'value': True,
    },
    'pipeline_manager_override': {
        'field': 'manager_override', 'operator': 'equals', 'value': True,
    },
    'pipeline_time_in_stage': {
        'field': 'time_in_stage_minutes', 'operator': 'gte', 'value': 0,
    },
}


def status_configurations(tenant_id):
    rows = LeadStatusConfiguration.query.filter_by(tenant_id=tenant_id).all()
    configured = {row.internal_key: row for row in rows}
    return [
        configured.get(key) or {
            'internal_key': key,
            'display_name': STATUS_LABELS[key],
            'display_order': index,
            'colour': '#64748b',
            'is_active': True,
            'pipeline_group': None,
            'is_qualified': key in ('interested', 'site_visit_planned', 'site_visit_done', 'negotiation', 'booking_done'),
            'is_lost': key in ('lost', 'junk', 'not_interested'),
            'is_terminal': key in ('booking_done', 'lost', 'junk', 'not_interested'),
            'is_success': key == 'booking_done',
            'entry_rule_keys': [],
            'exit_rule_keys': [],
            'required_action_type_keys': [],
            'default_actions': [],
            'visibility': 'VISIBLE',
        }
        for index, key in enumerate(VALID_STATUSES)
    ]


def active_rule(tenant_id, rule_key):
    row = (
        BusinessRuleConfiguration.query
        .filter_by(tenant_id=tenant_id, rule_key=rule_key, is_active=True)
        .order_by(BusinessRuleConfiguration.version.desc())
        .first()
    )
    return (row.definition if row else DEFAULT_RULES.get(rule_key, {})) or {}


def evaluate_rule(tenant_id, rule_key, context):
    definition = active_rule(tenant_id, rule_key)
    return evaluate_definition(definition, context)


def _value(context, path):
    current = context
    for part in str(path or '').split('.'):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _compare(actual, operator, expected):
    operator = str(operator or 'equals').lower()
    if operator in ('equals', 'eq'):
        return actual == expected
    if operator in ('not_equals', 'ne'):
        return actual != expected
    if operator == 'in':
        return actual in (expected or [])
    if operator == 'not_in':
        return actual not in (expected or [])
    if operator in ('gte', 'gt', 'lte', 'lt'):
        try:
            left, right = float(actual), float(expected)
        except (TypeError, ValueError):
            return False
        return {
            'gte': left >= right, 'gt': left > right,
            'lte': left <= right, 'lt': left < right,
        }[operator]
    if operator == 'exists':
        return (actual is not None) is bool(expected)
    if operator == 'contains':
        return expected in (actual or [])
    return False


def evaluate_definition(definition, context):
    """Evaluate a versioned rule definition without embedding business policy."""
    definition = definition or {}
    context = context or {}
    if 'all' in definition:
        return all(evaluate_definition(item, context) for item in definition['all'])
    if 'any' in definition:
        return any(evaluate_definition(item, context) for item in definition['any'])
    if 'not' in definition:
        return not evaluate_definition(definition['not'], context)
    if 'field' in definition:
        return _compare(
            _value(context, definition['field']),
            definition.get('operator'),
            definition.get('value'),
        )
    if 'status_in' in definition:
        return str(context.get('status') or '') in definition['status_in']
    if 'minutes' in definition:
        return float(context.get('age_minutes') or 0) >= float(definition['minutes'])
    if 'overdue_minutes' in definition:
        return float(context.get('overdue_minutes') or 0) >= float(definition['overdue_minutes'])
    if 'warning_minutes' in definition:
        return float(context.get('minutes_until') or 0) <= float(definition['warning_minutes'])
    return False


def evaluate_rules(tenant_id, rule_keys, context):
    """Return an auditable result for every configured rule key."""
    results = []
    for key in rule_keys or []:
        definition = active_rule(tenant_id, key)
        results.append({
            'rule_key': key,
            'matched': evaluate_definition(definition, context),
            'evaluated_at': datetime.utcnow().isoformat(),
        })
    return {
        'passed': all(item['matched'] for item in results),
        'results': results,
    }
