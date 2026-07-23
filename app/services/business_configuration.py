"""Backward-compatible configuration resolution and rule evaluation."""

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
    if 'status_in' in definition:
        return str(context.get('status') or '') in definition['status_in']
    if 'minutes' in definition:
        return float(context.get('age_minutes') or 0) >= float(definition['minutes'])
    if 'overdue_minutes' in definition:
        return float(context.get('overdue_minutes') or 0) >= float(definition['overdue_minutes'])
    if 'warning_minutes' in definition:
        return float(context.get('minutes_until') or 0) <= float(definition['warning_minutes'])
    return False
