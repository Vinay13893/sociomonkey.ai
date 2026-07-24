"""Tenant business-configuration administration APIs."""

from datetime import datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request

from app.middleware import require_capability
from app.models.activity import ActivityLog
from app.models.base import db
from app.models.business_configuration import (
    BusinessRuleConfiguration, LeadSourceConfiguration, LeadStatusConfiguration,
)
from app.models.ingestion import LeadSource
from app.models.project import Project
from app.models.user import User
from app.services.business_configuration import DEFAULT_RULES, evaluate_rule, status_configurations
from app.utils.leads import VALID_STATUSES


configuration_bp = Blueprint('configuration', __name__, url_prefix='/api/configuration')
VISIBILITY = {'VISIBLE', 'HIDDEN'}
RULE_KEYS = set(DEFAULT_RULES)


def _tenant_id():
    return request.current_user.tenant_id or getattr(request, 'current_tenant_id', None)


def _correlation_id():
    return str(request.headers.get('X-Correlation-ID') or uuid4())


def _audit(action, old, new, correlation_id):
    db.session.add(ActivityLog(
        tenant_id=_tenant_id(), user_id=request.current_user.id, action=action,
        module='configuration', resource_type='BusinessConfiguration',
        old_value=old, new_value=new, correlation_id=correlation_id,
        ip_address=request.remote_addr,
    ))


@configuration_bp.get('/lead-statuses')
@require_capability('configuration.view', 'TENANT')
def list_statuses():
    rows = status_configurations(_tenant_id())
    payload = [row.to_dict() if hasattr(row, 'to_dict') else row for row in rows]
    return jsonify({'statuses': sorted(payload, key=lambda row: row['display_order'])})


@configuration_bp.put('/lead-statuses/<string:internal_key>')
@require_capability('configuration.manage', 'TENANT')
def update_status(internal_key):
    if internal_key not in VALID_STATUSES:
        return jsonify({'error': 'Unknown immutable internal status key'}), 404
    data = request.get_json() or {}
    row = LeadStatusConfiguration.query.filter_by(
        tenant_id=_tenant_id(), internal_key=internal_key
    ).first()
    if not row:
        current = next(item for item in status_configurations(_tenant_id()) if item['internal_key'] == internal_key)
        row = LeadStatusConfiguration(tenant_id=_tenant_id(), internal_key=internal_key)
        for key, value in current.items():
            if key != 'internal_key':
                setattr(row, key, value)
        db.session.add(row)
    old = row.to_dict()
    for field in (
        'display_name', 'display_order', 'colour', 'is_active',
        'pipeline_group', 'is_qualified', 'is_lost', 'is_terminal',
        'is_success', 'entry_rule_keys', 'exit_rule_keys',
        'required_action_type_keys', 'default_actions', 'visibility',
    ):
        if field in data:
            setattr(row, field, data[field])
    for field in (
        'entry_rule_keys', 'exit_rule_keys', 'required_action_type_keys',
        'default_actions',
    ):
        if not isinstance(getattr(row, field), list):
            return jsonify({'error': f'{field} must be an array'}), 400
    unknown_rules = (
        set(row.entry_rule_keys or []) | set(row.exit_rule_keys or [])
    ) - RULE_KEYS
    if unknown_rules:
        return jsonify({
            'error': 'Unknown business rule key',
            'rule_keys': sorted(unknown_rules),
        }), 400
    if row.visibility not in VISIBILITY:
        return jsonify({'error': 'Invalid visibility'}), 400
    row.updated_by = request.current_user.id
    cid = _correlation_id()
    db.session.flush()
    _audit('lead_status_configuration_updated', old, row.to_dict(), cid)
    db.session.commit()
    return jsonify({'status': row.to_dict(), 'correlation_id': cid})


@configuration_bp.get('/lead-sources')
@require_capability('configuration.view', 'TENANT')
def list_sources():
    sources = LeadSource.query.filter_by(tenant_id=_tenant_id()).order_by(LeadSource.id).limit(500).all()
    configs = {r.lead_source_id: r for r in LeadSourceConfiguration.query.filter_by(tenant_id=_tenant_id()).all()}
    result = []
    for index, source in enumerate(sources):
        row = configs.get(source.id)
        result.append(row.to_dict() if row else {
            'lead_source_id': source.id, 'display_name': source.name,
            'display_order': index, 'is_active': source.is_active,
            'reporting_group': source.source_type, 'project_id': None,
            'manager_id': source.assign_manager_id, 'visibility': 'VISIBLE',
            'identity': {'source_type': source.source_type},
        })
    return jsonify({'sources': result})


@configuration_bp.put('/lead-sources/<int:source_id>')
@require_capability('configuration.manage', 'TENANT')
def update_source(source_id):
    source = LeadSource.query.filter_by(id=source_id, tenant_id=_tenant_id()).first()
    if not source:
        return jsonify({'error': 'Source not found'}), 404
    data = request.get_json() or {}
    if data.get('project_id') is not None and not Project.query.filter_by(
        id=data['project_id'], tenant_id=_tenant_id()
    ).first():
        return jsonify({'error': 'Project not found in tenant'}), 400
    if data.get('manager_id') is not None and not User.query.filter_by(
        id=data['manager_id'], tenant_id=_tenant_id()
    ).first():
        return jsonify({'error': 'Manager not found in tenant'}), 400
    row = LeadSourceConfiguration.query.filter_by(
        tenant_id=_tenant_id(), lead_source_id=source.id
    ).first()
    if not row:
        row = LeadSourceConfiguration(
            tenant_id=_tenant_id(), lead_source_id=source.id,
            display_name=source.name, is_active=source.is_active,
            reporting_group=source.source_type, manager_id=source.assign_manager_id,
        )
        db.session.add(row)
    old = row.to_dict()
    for field in ('display_name','display_order','is_active','reporting_group',
                  'project_id','manager_id','visibility'):
        if field in data:
            setattr(row, field, data[field])
    if row.visibility not in VISIBILITY:
        return jsonify({'error': 'Invalid visibility'}), 400
    row.updated_by = request.current_user.id
    cid = _correlation_id()
    db.session.flush()
    _audit('lead_source_configuration_updated', old, row.to_dict(), cid)
    db.session.commit()
    return jsonify({'source': row.to_dict(), 'correlation_id': cid})


@configuration_bp.get('/business-rules')
@require_capability('configuration.view', 'TENANT')
def list_rules():
    rows = BusinessRuleConfiguration.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    ).order_by(BusinessRuleConfiguration.rule_key, BusinessRuleConfiguration.version.desc()).all()
    latest = {}
    for row in rows:
        latest.setdefault(row.rule_key, row.to_dict())
    for key, definition in DEFAULT_RULES.items():
        latest.setdefault(key, {'rule_key': key, 'display_name': key.replace('_',' ').title(),
                                'version': 0, 'definition': definition, 'is_active': True})
    return jsonify({'rules': list(latest.values())})


@configuration_bp.put('/business-rules/<string:rule_key>')
@require_capability('configuration.manage', 'TENANT')
def update_rule(rule_key):
    if rule_key not in RULE_KEYS:
        return jsonify({'error': 'Unknown rule key'}), 404
    data = request.get_json() or {}
    if not isinstance(data.get('definition'), dict):
        return jsonify({'error': 'definition must be an object'}), 400
    current = BusinessRuleConfiguration.query.filter_by(
        tenant_id=_tenant_id(), rule_key=rule_key, is_active=True
    ).order_by(BusinessRuleConfiguration.version.desc()).first()
    old = current.to_dict() if current else {'definition': DEFAULT_RULES[rule_key], 'version': 0}
    version = (current.version if current else 0) + 1
    if current:
        current.is_active = False
        current.effective_to = datetime.utcnow()
    row = BusinessRuleConfiguration(
        tenant_id=_tenant_id(), rule_key=rule_key,
        display_name=data.get('display_name') or rule_key.replace('_',' ').title(),
        version=version, definition=data['definition'], created_by=request.current_user.id,
    )
    db.session.add(row)
    cid = _correlation_id()
    db.session.flush()
    _audit('business_rule_configuration_updated', old, row.to_dict(), cid)
    db.session.commit()
    return jsonify({'rule': row.to_dict(), 'correlation_id': cid})


@configuration_bp.post('/business-rules/<string:rule_key>/evaluate')
@require_capability('configuration.view', 'TENANT')
def evaluate(rule_key):
    if rule_key not in RULE_KEYS:
        return jsonify({'error': 'Unknown rule key'}), 404
    return jsonify({'rule_key': rule_key, 'matched': evaluate_rule(
        _tenant_id(), rule_key, request.get_json() or {}
    )})
