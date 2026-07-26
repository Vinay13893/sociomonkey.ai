"""Unified, capability-scoped operational Action Board APIs."""

from datetime import datetime, timedelta
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import joinedload

from app.middleware import require_capability
from app.models.action_item import (
    ActionItem,
    ActionPriorityConfiguration,
    ActionStatusConfiguration,
    ActionTypeConfiguration,
)
from app.models.activity import ActivityLog
from app.models.base import db
from app.models.business_configuration import BusinessRuleConfiguration
from app.models.channel_partner import (
    ChannelPartner, ChannelPartnerAssignment,
)
from app.models.lead import CallbackReminder, Lead
from app.models.location import Location
from app.models.organisation import (
    BusinessRole, OrganisationUnit, OrganisationUnitMembership,
    ReportingRelationship, UserBusinessRole,
)
from app.models.project import Project
from app.models.user import User
from app.models.visit import Visit
from app.services.action_item_events import notify_action_item
from app.services.permissions import capability_decision
from app.utils.time_utils import (
    business_date_bounds_utc_naive,
    parse_business_datetime_to_utc_naive,
)


action_items_bp = Blueprint(
    'action_items', __name__, url_prefix='/api/action-items'
)

SOURCE_TYPES = {
    'LEAD', 'VISIT', 'RECEPTION', 'CHANNEL_PARTNER', 'BUSINESS_RULE',
    'SLA', 'CALLBACK', 'MANUAL', 'AUTOMATION',
}
TERMINAL_STATUSES = {'COMPLETED', 'CANCELLED', 'EXPIRED'}
VISIBILITY_VALUES = {'VISIBLE', 'HIDDEN'}
CONFIG_MODELS = {
    'types': ActionTypeConfiguration,
    'statuses': ActionStatusConfiguration,
    'priorities': ActionPriorityConfiguration,
}
CONFIG_FIELDS = {
    'types': {
        'display_name', 'display_order', 'colour', 'icon',
        'default_priority_key', 'is_active', 'visibility',
    },
    'statuses': {
        'display_name', 'display_order', 'colour', 'is_active',
        'is_terminal', 'visibility',
    },
    'priorities': {
        'display_name', 'display_order', 'weight', 'colour', 'is_default',
        'is_active', 'visibility',
    },
}


def _tenant_id():
    return request.current_user.tenant_id or getattr(
        request, 'current_tenant_id', None
    )


def _cid():
    return str(request.headers.get('X-Correlation-ID') or uuid4())


def _audit(action, row, old, new, correlation_id, resource_type='ActionItem'):
    db.session.add(ActivityLog(
        tenant_id=_tenant_id(),
        user_id=request.current_user.id,
        action=action,
        module='action_items',
        resource_type=resource_type,
        resource_id=getattr(row, 'id', None),
        old_value=old,
        new_value=new,
        correlation_id=correlation_id,
        ip_address=request.remote_addr,
    ))


def _page_args():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 25, type=int)))
    return page, per_page


def _active_reporting_user_ids(user_id):
    now = datetime.utcnow()
    rows = ReportingRelationship.query.with_entities(
        ReportingRelationship.user_id
    ).filter(
        ReportingRelationship.tenant_id == _tenant_id(),
        ReportingRelationship.manager_id == user_id,
        ReportingRelationship.is_active == True,  # noqa: E712
        ReportingRelationship.effective_from <= now,
        or_(
            ReportingRelationship.effective_to.is_(None),
            ReportingRelationship.effective_to > now,
        ),
    ).all()
    ids = {user_id, *(row[0] for row in rows)}
    legacy = User.query.with_entities(User.id).filter(
        User.tenant_id == _tenant_id(),
        User.is_active == True,  # noqa: E712
        or_(User.manager_id == user_id, User.assigned_manager_id == user_id),
    ).all()
    ids.update(row[0] for row in legacy)
    return ids


def _user_unit_ids(user_id):
    now = datetime.utcnow()
    memberships = OrganisationUnitMembership.query.with_entities(
        OrganisationUnitMembership.organisation_unit_id
    ).filter(
        OrganisationUnitMembership.tenant_id == _tenant_id(),
        OrganisationUnitMembership.user_id == user_id,
        OrganisationUnitMembership.is_active == True,  # noqa: E712
        OrganisationUnitMembership.effective_from <= now,
        or_(
            OrganisationUnitMembership.effective_to.is_(None),
            OrganisationUnitMembership.effective_to > now,
        ),
    ).all()
    roles = UserBusinessRole.query.with_entities(
        UserBusinessRole.organisation_unit_id
    ).filter(
        UserBusinessRole.tenant_id == _tenant_id(),
        UserBusinessRole.user_id == user_id,
        UserBusinessRole.is_active == True,  # noqa: E712
        UserBusinessRole.organisation_unit_id.isnot(None),
        UserBusinessRole.effective_from <= now,
        or_(
            UserBusinessRole.effective_to.is_(None),
            UserBusinessRole.effective_to > now,
        ),
    ).all()
    return {
        row[0] for row in [*memberships, *roles] if row[0] is not None
    }


def _visibility():
    scope = (getattr(request, 'permission_decision', {}) or {}).get(
        'scope'
    ) or 'OWN'
    user_id = request.current_user.id
    if scope in {'TENANT', 'PLATFORM'}:
        return scope, None, None
    if scope == 'TEAM':
        return scope, _active_reporting_user_ids(user_id), _user_unit_ids(user_id)
    if scope == 'ORGANISATION_UNIT':
        units = _user_unit_ids(user_id)
        users = {user_id}
        if units:
            rows = OrganisationUnitMembership.query.with_entities(
                OrganisationUnitMembership.user_id
            ).filter(
                OrganisationUnitMembership.tenant_id == _tenant_id(),
                OrganisationUnitMembership.organisation_unit_id.in_(units),
                OrganisationUnitMembership.is_active == True,  # noqa: E712
            ).all()
            users.update(row[0] for row in rows)
        return scope, users, units
    return 'OWN', {user_id}, _user_unit_ids(user_id)


def _visible_query(include_inactive=False):
    query = ActionItem.query.filter(ActionItem.tenant_id == _tenant_id())
    if not include_inactive:
        query = query.filter(ActionItem.is_active == True)  # noqa: E712
    scope, user_ids, unit_ids = _visibility()
    if scope not in {'TENANT', 'PLATFORM'}:
        clauses = [ActionItem.assigned_user_id.in_(user_ids or set())]
        if unit_ids:
            clauses.append(ActionItem.organisation_unit_id.in_(unit_ids))
        query = query.filter(or_(*clauses))
    return query


def _target_allowed(user_id=None, organisation_unit_id=None):
    decision = capability_decision(
        request.current_user, 'action_items.assign', 'OWN'
    )
    if not decision['allowed']:
        return user_id in (None, request.current_user.id) and not organisation_unit_id
    scope = decision.get('scope') or 'OWN'
    if scope in {'TENANT', 'PLATFORM'}:
        return True
    if organisation_unit_id and organisation_unit_id not in _user_unit_ids(
        request.current_user.id
    ):
        return False
    if user_id is None:
        return True
    if scope == 'OWN':
        return user_id == request.current_user.id
    if scope == 'TEAM':
        return user_id in _active_reporting_user_ids(request.current_user.id)
    if scope == 'ORGANISATION_UNIT':
        unit_ids = _user_unit_ids(request.current_user.id)
        return bool(
            OrganisationUnitMembership.query.filter(
                OrganisationUnitMembership.tenant_id == _tenant_id(),
                OrganisationUnitMembership.user_id == user_id,
                OrganisationUnitMembership.organisation_unit_id.in_(unit_ids),
                OrganisationUnitMembership.is_active == True,  # noqa: E712
            ).first()
        )
    return False


def _reference(model, value, label, active_only=False):
    if value in (None, ''):
        return None
    query = model.query.filter_by(id=int(value), tenant_id=_tenant_id())
    if active_only and hasattr(model, 'is_active'):
        query = query.filter_by(is_active=True)
    row = query.first()
    if not row:
        raise ValueError(f'{label} was not found in this tenant')
    return row


def _configuration(model, key, label, allow_inactive=None):
    internal_key = str(key or '').strip().upper()
    row = model.query.filter_by(
        tenant_id=_tenant_id(), internal_key=internal_key
    ).first()
    if not row or (
        not row.is_active and internal_key != str(allow_inactive or '').upper()
    ):
        raise ValueError(f'{label} is not active for this tenant')
    return row


def _parse_due(value):
    if value in (None, ''):
        return None
    try:
        return parse_business_datetime_to_utc_naive(value)
    except ValueError as exc:
        raise ValueError('Due date/time must be an ISO-8601 value') from exc


def _source_context(source_type, source_id, active_only=True):
    source_type = str(source_type or '').strip().upper()
    if source_type not in SOURCE_TYPES:
        raise ValueError('Unsupported Action Item source type')
    if source_type == 'MANUAL':
        if source_id not in (None, ''):
            raise ValueError('Manual Actions must not reference another record')
        return source_type, None, {}
    if source_type == 'AUTOMATION':
        raise ValueError(
            'Automation source is reserved until an automation record exists'
        )
    if source_id in (None, ''):
        raise ValueError(f'{source_type} source_id is required')
    source_id = int(source_id)
    if source_type == 'LEAD':
        row = _reference(Lead, source_id, 'Lead', active_only=active_only)
        return source_type, row.id, {
            'title': f'Follow up with {row.name}',
            'project_id': row.project_id,
            'assigned_user_id': row.assigned_to,
            'action_type_key': 'CALL',
        }
    if source_type in {'VISIT', 'RECEPTION'}:
        row = _reference(Visit, source_id, 'Visit', active_only=active_only)
        return source_type, row.id, {
            'title': row.purpose or f'Visit #{row.id}',
            'project_id': row.project_id,
            'location_id': row.location_id,
            'assigned_user_id': row.assigned_user_id,
            'due_at': row.expected_arrival,
            'action_type_key': 'GALLERY_VISIT',
        }
    if source_type == 'CHANNEL_PARTNER':
        row = _reference(
            ChannelPartner, source_id, 'Channel Partner',
            active_only=active_only,
        )
        assignment = ChannelPartnerAssignment.query.filter(
            ChannelPartnerAssignment.tenant_id == _tenant_id(),
            ChannelPartnerAssignment.channel_partner_id == row.id,
            ChannelPartnerAssignment.is_active == True,  # noqa: E712
            ChannelPartnerAssignment.assignment_type.in_(
                {'RELATIONSHIP_MANAGER', 'SALES_MANAGER'}
            ),
        ).order_by(
            case(
                (
                    ChannelPartnerAssignment.assignment_type
                    == 'RELATIONSHIP_MANAGER',
                    0,
                ),
                else_=1,
            )
        ).first()
        return source_type, row.id, {
            'title': f'Follow up with {row.name}',
            'assigned_user_id': assignment.user_id if assignment else None,
            'action_type_key': 'FOLLOW_UP',
        }
    if source_type in {'BUSINESS_RULE', 'SLA'}:
        row = _reference(
            BusinessRuleConfiguration, source_id, 'Business Rule',
            active_only=active_only,
        )
        return source_type, row.id, {
            'title': row.display_name,
            'action_type_key': 'REMINDER',
        }
    if source_type == 'CALLBACK':
        row = _reference(CallbackReminder, source_id, 'Callback')
        lead = _reference(
            Lead, row.lead_id, 'Callback Lead', active_only=active_only
        )
        return source_type, row.id, {
            'title': f'Callback: {lead.name}',
            'project_id': lead.project_id,
            'assigned_user_id': row.assigned_user_id,
            'due_at': row.callback_datetime,
            'action_type_key': 'CALL',
        }
    raise ValueError('Unsupported Action Item source')


def _validate_payload(data, current=None):
    source_type = data.get(
        'source_type', current.source_type if current else 'MANUAL'
    )
    source_id = data.get(
        'source_id', current.source_id if current else None
    )
    normalized_source_id = (
        None if source_id in (None, '') else int(source_id)
    )
    if current and (
        str(source_type or '').strip().upper() != current.source_type
        or normalized_source_id != current.source_id
    ):
        raise ValueError('Action source identity cannot be changed')
    source_type, source_id, context = _source_context(
        source_type, normalized_source_id, active_only=current is None
    )
    action_type = _configuration(
        ActionTypeConfiguration,
        data.get(
            'action_type_key',
            current.action_type_key if current else context.get(
                'action_type_key', 'INTERNAL_TASK'
            ),
        ),
        'Action type',
        current.action_type_key if current else None,
    )
    status = _configuration(
        ActionStatusConfiguration,
        data.get(
            'status_key', current.status_key if current else 'PENDING'
        ),
        'Action status',
        current.status_key if current else None,
    )
    priority = _configuration(
        ActionPriorityConfiguration,
        data.get(
            'priority_key',
            current.priority_key if current else action_type.default_priority_key,
        ),
        'Action priority',
        current.priority_key if current else None,
    )
    assigned_value = data.get(
        'assigned_user_id',
        current.assigned_user_id if current else context.get('assigned_user_id'),
    )
    unit_value = data.get(
        'organisation_unit_id',
        current.organisation_unit_id if current else None,
    )
    assigned = _reference(User, assigned_value, 'Assigned user', active_only=True)
    unit = _reference(
        OrganisationUnit, unit_value, 'Organisation unit', active_only=True
    )
    if assigned and not _target_allowed(assigned.id, unit.id if unit else None):
        raise PermissionError('Action assignment is outside your permitted scope')
    if unit and not _target_allowed(
        assigned.id if assigned else None, unit.id
    ):
        raise PermissionError('Team assignment is outside your permitted scope')
    project = _reference(
        Project,
        data.get(
            'project_id',
            current.project_id if current else context.get('project_id'),
        ),
        'Project',
        active_only=True,
    )
    location = _reference(
        Location,
        data.get(
            'location_id',
            current.location_id if current else context.get('location_id'),
        ),
        'Location',
        active_only=True,
    )
    title = str(
        data.get(
            'title', current.title if current else context.get('title', '')
        ) or ''
    ).strip()
    if not title:
        raise ValueError('Action title is required')
    if len(title) > 240:
        raise ValueError('Action title must be 240 characters or fewer')
    due_raw = data.get(
        'due_at',
        current.due_at if current else context.get('due_at'),
    )
    due_at = due_raw if isinstance(due_raw, datetime) else _parse_due(due_raw)
    return {
        'source_type': source_type,
        'source_id': source_id,
        'action_type_key': action_type.internal_key,
        'status_key': status.internal_key,
        'priority_key': priority.internal_key,
        'title': title,
        'description': str(data.get(
            'description', current.description if current else ''
        ) or '').strip() or None,
        'assigned_user_id': assigned.id if assigned else None,
        'organisation_unit_id': unit.id if unit else None,
        'project_id': project.id if project else None,
        'location_id': location.id if location else None,
        'due_at': due_at,
        'business_rule_priority': max(
            0, int(data.get(
                'business_rule_priority',
                current.business_rule_priority if current else 0,
            ) or 0),
        ),
    }


def _configuration_maps():
    result = {}
    for name, model in CONFIG_MODELS.items():
        rows = model.query.filter_by(tenant_id=_tenant_id()).order_by(
            model.display_order, model.id
        ).all()
        result[name] = [row.to_dict() for row in rows]
    return result


def _board_profile():
    assignment = UserBusinessRole.query.options(
        joinedload(UserBusinessRole.business_role)
    ).filter_by(
        tenant_id=_tenant_id(), user_id=request.current_user.id,
        is_active=True,
    ).order_by(
        UserBusinessRole.is_primary.desc(), UserBusinessRole.id
    ).first()
    role = assignment.business_role if assignment else None
    capabilities = {}
    for action, capability in {
        'create': 'action_items.create',
        'edit': 'action_items.edit',
        'assign': 'action_items.assign',
        'complete': 'action_items.complete',
        'archive': 'action_items.archive',
        'configure': 'action_items.configure',
    }.items():
        capabilities[action] = capability_decision(
            request.current_user, capability, 'OWN'
        )['allowed']
    return {
        'role_key': role.key if role else request.current_user.role.upper(),
        'role_name': (
            role.display_name if role else
            str(request.current_user.role).replace('_', ' ').title()
        ),
        'visibility_scope': _visibility()[0],
        'capabilities': capabilities,
    }


def _source_summaries(rows):
    ids = {}
    for row in rows:
        if row.source_id:
            ids.setdefault(row.source_type, set()).add(row.source_id)
    summaries = {}
    model_fields = {
        'LEAD': (Lead, 'name'),
        'VISIT': (Visit, 'purpose'),
        'RECEPTION': (Visit, 'purpose'),
        'CHANNEL_PARTNER': (ChannelPartner, 'name'),
        'BUSINESS_RULE': (BusinessRuleConfiguration, 'display_name'),
        'SLA': (BusinessRuleConfiguration, 'display_name'),
        'CALLBACK': (CallbackReminder, 'notes'),
    }
    for source_type, source_ids in ids.items():
        details = model_fields.get(source_type)
        if not details:
            continue
        model, name_field = details
        source_rows = model.query.filter(
            model.id.in_(source_ids),
            model.tenant_id == _tenant_id(),
        ).all()
        for source in source_rows:
            label = getattr(source, name_field, None)
            if not label:
                label = f'{source_type.replace("_", " ").title()} #{source.id}'
            summaries[(source_type, source.id)] = {
                'type': source_type,
                'id': source.id,
                'label': label,
            }
    return summaries


def _serialize_rows(rows):
    configurations = _configuration_maps()
    type_map = {
        row['internal_key']: row for row in configurations['types']
    }
    status_map = {
        row['internal_key']: row for row in configurations['statuses']
    }
    priority_map = {
        row['internal_key']: row for row in configurations['priorities']
    }
    sources = _source_summaries(rows)
    result = []
    for row in rows:
        payload = row.to_dict()
        payload.update({
            'action_type': type_map.get(row.action_type_key),
            'status': status_map.get(row.status_key),
            'priority': priority_map.get(row.priority_key),
            'source': sources.get((row.source_type, row.source_id), {
                'type': row.source_type,
                'id': row.source_id,
                'label': 'Manual action' if row.source_type == 'MANUAL' else None,
            }),
        })
        result.append(payload)
    return result


def _apply_filters(query):
    args = request.args
    scalar_filters = {
        'assigned_user_id': ActionItem.assigned_user_id,
        'organisation_unit_id': ActionItem.organisation_unit_id,
        'project_id': ActionItem.project_id,
        'location_id': ActionItem.location_id,
        'lead_id': ActionItem.source_id,
        'visit_id': ActionItem.source_id,
        'channel_partner_id': ActionItem.source_id,
    }
    for parameter, column in scalar_filters.items():
        value = args.get(parameter, type=int)
        if value is not None:
            query = query.filter(column == value)
            if parameter == 'lead_id':
                query = query.filter(ActionItem.source_type == 'LEAD')
            elif parameter == 'visit_id':
                query = query.filter(
                    ActionItem.source_type.in_({'VISIT', 'RECEPTION'})
                )
            elif parameter == 'channel_partner_id':
                query = query.filter(
                    ActionItem.source_type == 'CHANNEL_PARTNER'
                )
    if args.get('status'):
        query = query.filter(
            ActionItem.status_key == args['status'].strip().upper()
        )
    if args.get('priority'):
        query = query.filter(
            ActionItem.priority_key == args['priority'].strip().upper()
        )
    if args.get('source_type'):
        query = query.filter(
            ActionItem.source_type == args['source_type'].strip().upper()
        )
    date_from = args.get('date_from')
    date_to = args.get('date_to')
    if date_from:
        try:
            query = query.filter(
                ActionItem.due_at >= datetime.strptime(date_from, '%Y-%m-%d')
            )
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(
                ActionItem.due_at
                < datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            )
        except ValueError:
            pass
    if args.get('due_today', '').lower() == 'true':
        start, end = business_date_bounds_utc_naive()
        query = query.filter(ActionItem.due_at >= start, ActionItem.due_at < end)
    if args.get('overdue', '').lower() == 'true':
        query = query.filter(
            ActionItem.due_at < datetime.utcnow(),
            ~ActionItem.status_key.in_(TERMINAL_STATUSES),
        )
    if args.get('completed', '').lower() == 'true':
        query = query.filter(ActionItem.status_key == 'COMPLETED')
    if args.get('high_priority', '').lower() == 'true':
        query = query.filter(ActionItem.priority_key.in_({'HIGH', 'URGENT'}))
    if args.get('recently_assigned', '').lower() == 'true':
        query = query.filter(
            ActionItem.assigned_at >= datetime.utcnow() - timedelta(hours=24)
        )
    search = str(args.get('search') or '').strip()
    if search:
        pattern = f'%{search[:120]}%'
        query = query.filter(or_(
            ActionItem.title.ilike(pattern),
            ActionItem.description.ilike(pattern),
        ))
    return query


def _item(item_id, include_inactive=False):
    return _visible_query(include_inactive=include_inactive).options(
        joinedload(ActionItem.assigned_user),
        joinedload(ActionItem.assigned_by_user),
        joinedload(ActionItem.organisation_unit),
        joinedload(ActionItem.project),
        joinedload(ActionItem.location),
    ).filter(ActionItem.id == item_id).first()


@action_items_bp.get('/configuration')
@require_capability('action_items.view', 'OWN')
def list_configuration():
    return jsonify({'configuration': _configuration_maps()})


@action_items_bp.post('/configuration/<string:kind>')
@require_capability('action_items.configure', 'TENANT')
def create_configuration(kind):
    model = CONFIG_MODELS.get(kind)
    if not model:
        return jsonify({'error': 'Unknown Action Board configuration type'}), 404
    data = request.get_json() or {}
    key = str(data.get('internal_key') or '').strip().upper()
    if not key or not key.replace('_', '').isalnum():
        return jsonify({'error': 'Internal key must use letters, numbers and underscores'}), 400
    if model.query.filter_by(tenant_id=_tenant_id(), internal_key=key).first():
        return jsonify({'error': 'Internal key already exists'}), 409
    row = model(
        tenant_id=_tenant_id(),
        internal_key=key,
        display_name=str(data.get('display_name') or key.replace('_', ' ').title()),
        updated_by=request.current_user.id,
    )
    row.display_order = int(data.get('display_order', 0) or 0)
    row.colour = str(data.get('colour') or '#64748b')
    row.is_active = bool(data.get('is_active', True))
    row.visibility = str(data.get('visibility') or 'VISIBLE').upper()
    if kind == 'types':
        row.default_priority_key = str(
            data.get('default_priority_key') or 'NORMAL'
        ).upper()
    elif kind == 'statuses':
        row.is_terminal = bool(data.get('is_terminal', False))
    else:
        row.weight = int(data.get('weight', 0) or 0)
        row.is_default = bool(data.get('is_default', False))
    for field in CONFIG_FIELDS[kind]:
        if field in data:
            setattr(row, field, data[field])
    if row.visibility not in VISIBILITY_VALUES:
        return jsonify({'error': 'Invalid visibility'}), 400
    if kind == 'types':
        try:
            _configuration(
                ActionPriorityConfiguration, row.default_priority_key,
                'Default Action priority',
            )
        except ValueError as exc:
            db.session.rollback()
            return jsonify({'error': str(exc)}), 400
    if kind == 'priorities' and row.is_default:
        model.query.filter_by(
            tenant_id=_tenant_id(), is_default=True
        ).update({'is_default': False}, synchronize_session=False)
    db.session.add(row)
    cid = _cid()
    db.session.flush()
    _audit(
        f'action_{kind}_configuration_created', row, None, row.to_dict(), cid,
        resource_type=model.__name__,
    )
    db.session.commit()
    return jsonify({'configuration': row.to_dict(), 'correlation_id': cid}), 201


@action_items_bp.put(
    '/configuration/<string:kind>/<string:internal_key>'
)
@require_capability('action_items.configure', 'TENANT')
def update_configuration(kind, internal_key):
    model = CONFIG_MODELS.get(kind)
    if not model:
        return jsonify({'error': 'Unknown Action Board configuration type'}), 404
    row = model.query.filter_by(
        tenant_id=_tenant_id(), internal_key=internal_key.upper()
    ).first()
    if not row:
        return jsonify({'error': 'Configuration not found'}), 404
    data = request.get_json() or {}
    old = row.to_dict()
    for field in CONFIG_FIELDS[kind]:
        if field in data:
            setattr(row, field, data[field])
    if row.visibility not in VISIBILITY_VALUES:
        return jsonify({'error': 'Invalid visibility'}), 400
    if kind == 'types':
        try:
            _configuration(
                ActionPriorityConfiguration, row.default_priority_key,
                'Default Action priority',
            )
        except ValueError as exc:
            db.session.rollback()
            return jsonify({'error': str(exc)}), 400
    if kind == 'priorities' and row.is_default:
        model.query.filter(
            model.tenant_id == _tenant_id(),
            model.id != row.id,
            model.is_default == True,  # noqa: E712
        ).update({'is_default': False}, synchronize_session=False)
    row.updated_by = request.current_user.id
    cid = _cid()
    _audit(
        f'action_{kind}_configuration_updated', row, old, row.to_dict(), cid,
        resource_type=model.__name__,
    )
    db.session.commit()
    return jsonify({'configuration': row.to_dict(), 'correlation_id': cid})


@action_items_bp.get('/references')
@require_capability('action_items.view', 'OWN')
def references():
    scope, user_ids, unit_ids = _visibility()
    users = User.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    )
    units = OrganisationUnit.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    )
    if scope not in {'TENANT', 'PLATFORM'}:
        users = users.filter(User.id.in_(user_ids or set()))
        units = units.filter(OrganisationUnit.id.in_(unit_ids or set()))
    return jsonify({
        'users': [
            {'id': row.id, 'name': row.name}
            for row in users.order_by(User.name).limit(500).all()
        ],
        'organisation_units': [
            {'id': row.id, 'name': row.name}
            for row in units.order_by(OrganisationUnit.name).limit(250).all()
        ],
        'projects': [
            {'id': row.id, 'name': row.name}
            for row in Project.query.filter_by(
                tenant_id=_tenant_id(), is_active=True
            ).order_by(Project.name).limit(500).all()
        ],
        'locations': [
            {'id': row.id, 'name': row.name}
            for row in Location.query.filter_by(
                tenant_id=_tenant_id(), is_active=True
            ).order_by(Location.name).limit(500).all()
        ],
        'configuration': _configuration_maps(),
        'board_profile': _board_profile(),
    })


@action_items_bp.get('')
@require_capability('action_items.view', 'OWN')
def list_action_items():
    page, per_page = _page_args()
    query = _apply_filters(_visible_query())
    total = int(query.order_by(None).with_entities(
        func.count(ActionItem.id)
    ).scalar() or 0)
    rows = query.options(
        joinedload(ActionItem.assigned_user),
        joinedload(ActionItem.assigned_by_user),
        joinedload(ActionItem.organisation_unit),
        joinedload(ActionItem.project),
        joinedload(ActionItem.location),
    ).order_by(
        case((ActionItem.due_at.is_(None), 1), else_=0),
        ActionItem.due_at,
        ActionItem.business_rule_priority.desc(),
        ActionItem.id.desc(),
    ).offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'action_items': _serialize_rows(rows),
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': max(1, (total + per_page - 1) // per_page),
        },
        'board_profile': _board_profile(),
    })


@action_items_bp.get('/dashboard')
@require_capability('action_items.view', 'OWN')
def action_dashboard():
    now = datetime.utcnow()
    start, end = business_date_bounds_utc_naive()
    base = _visible_query()
    metrics = base.with_entities(
        func.count(ActionItem.id).label('my_actions'),
        func.coalesce(func.sum(case((
            and_(ActionItem.due_at >= start, ActionItem.due_at < end),
            1,
        ), else_=0)), 0).label('due_today'),
        func.coalesce(func.sum(case((
            and_(
                ActionItem.due_at < now,
                ~ActionItem.status_key.in_(TERMINAL_STATUSES),
            ),
            1,
        ), else_=0)), 0).label('overdue'),
        func.coalesce(func.sum(case((
            ActionItem.status_key == 'WAITING', 1
        ), else_=0)), 0).label('waiting'),
        func.coalesce(func.sum(case((
            and_(
                ActionItem.completed_at >= start,
                ActionItem.completed_at < end,
            ),
            1,
        ), else_=0)), 0).label('completed_today'),
        func.coalesce(func.sum(case((
            ActionItem.priority_key.in_({'HIGH', 'URGENT'}), 1
        ), else_=0)), 0).label('high_priority'),
        func.coalesce(func.sum(case((
            ActionItem.assigned_at >= now - timedelta(hours=24), 1
        ), else_=0)), 0).label('recently_assigned'),
    ).first()
    return jsonify({
        'metrics': {
            key: int(getattr(metrics, key) or 0)
            for key in (
                'my_actions', 'due_today', 'overdue', 'waiting',
                'completed_today', 'high_priority', 'recently_assigned',
            )
        },
        'board_profile': _board_profile(),
    })


def _create_action(data):
    values = _validate_payload(data)
    idempotency_key = str(data.get('idempotency_key') or '').strip() or None
    if idempotency_key:
        existing = ActionItem.query.filter_by(
            tenant_id=_tenant_id(), idempotency_key=idempotency_key
        ).first()
        if existing:
            return existing, False, None
    now = datetime.utcnow()
    row = ActionItem(
        tenant_id=_tenant_id(),
        idempotency_key=idempotency_key,
        assigned_by_user_id=(
            request.current_user.id if values['assigned_user_id'] else None
        ),
        assigned_at=now if values['assigned_user_id'] else None,
        created_by=request.current_user.id,
        updated_by=request.current_user.id,
        **values,
    )
    db.session.add(row)
    cid = _cid()
    db.session.flush()
    _audit('action_item_created', row, None, row.to_dict(), cid)
    if row.assigned_user_id:
        notify_action_item(
            row, row.assigned_user, 'assigned', cid,
            idempotency_key=f'action:{row.id}:assigned:{row.assigned_user_id}:1',
        )
    db.session.commit()
    return row, True, cid


@action_items_bp.post('')
@require_capability('action_items.create', 'OWN')
def create_action_item():
    try:
        row, created, cid = _create_action(request.get_json() or {})
    except PermissionError as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 403
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400
    return jsonify({
        'action_item': _serialize_rows([row])[0],
        'created': created,
        'correlation_id': cid,
    }), 201 if created else 200


@action_items_bp.post('/generate')
@require_capability('action_items.create', 'OWN')
def generate_action_item():
    """Idempotently generate an Action from an existing platform entity."""
    data = request.get_json() or {}
    if str(data.get('source_type') or '').upper() == 'MANUAL':
        return jsonify({'error': 'Use the Action Item create endpoint for manual work'}), 400
    try:
        row, created, cid = _create_action(data)
    except PermissionError as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 403
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400
    return jsonify({
        'action_item': _serialize_rows([row])[0],
        'created': created,
        'correlation_id': cid,
    }), 201 if created else 200


@action_items_bp.get('/<int:item_id>')
@require_capability('action_items.view', 'OWN')
def get_action_item(item_id):
    row = _item(item_id, include_inactive=True)
    if not row:
        return jsonify({'error': 'Action Item not found'}), 404
    return jsonify({'action_item': _serialize_rows([row])[0]})


@action_items_bp.put('/<int:item_id>')
@require_capability('action_items.edit', 'OWN')
def update_action_item(item_id):
    row = _item(item_id)
    if not row:
        return jsonify({'error': 'Action Item not found'}), 404
    data = request.get_json() or {}
    if 'status_key' in data or 'assigned_user_id' in data:
        return jsonify({
            'error': 'Use the lifecycle or assignment endpoint for this change'
        }), 400
    old = row.to_dict()
    try:
        values = _validate_payload(data, current=row)
    except PermissionError as exc:
        return jsonify({'error': str(exc)}), 403
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_by = request.current_user.id
    cid = _cid()
    _audit('action_item_updated', row, old, row.to_dict(), cid)
    db.session.commit()
    return jsonify({
        'action_item': _serialize_rows([row])[0],
        'correlation_id': cid,
    })


@action_items_bp.post('/<int:item_id>/assign')
@require_capability('action_items.assign', 'OWN')
def assign_action_item(item_id):
    row = _item(item_id)
    if not row:
        return jsonify({'error': 'Action Item not found'}), 404
    data = request.get_json() or {}
    try:
        user = _reference(
            User, data.get('assigned_user_id'), 'Assigned user',
            active_only=True,
        )
        unit = _reference(
            OrganisationUnit, data.get('organisation_unit_id'),
            'Organisation unit', active_only=True,
        )
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400
    if not user and not unit:
        return jsonify({'error': 'A user or organisation unit is required'}), 400
    if not _target_allowed(
        user.id if user else None, unit.id if unit else None
    ):
        return jsonify({'error': 'Assignment is outside your permitted scope'}), 403
    old = row.to_dict()
    previous_user_id = row.assigned_user_id
    row.assigned_user_id = user.id if user else None
    row.organisation_unit_id = unit.id if unit else None
    row.assigned_by_user_id = request.current_user.id
    row.assigned_at = datetime.utcnow()
    row.updated_by = request.current_user.id
    cid = _cid()
    action = (
        'action_item_reassigned' if previous_user_id
        and previous_user_id != row.assigned_user_id
        else 'action_item_assigned'
    )
    _audit(action, row, old, row.to_dict(), cid)
    if user:
        notify_action_item(
            row, user,
            'reassigned' if previous_user_id else 'assigned',
            cid,
            idempotency_key=(
                f'action:{row.id}:assignment:{row.assigned_at.isoformat()}'
            ),
        )
    db.session.commit()
    return jsonify({
        'action_item': _serialize_rows([row])[0],
        'correlation_id': cid,
    })


@action_items_bp.post('/<int:item_id>/status')
@require_capability('action_items.complete', 'OWN')
def change_action_status(item_id):
    row = _item(item_id)
    if not row:
        return jsonify({'error': 'Action Item not found'}), 404
    data = request.get_json() or {}
    try:
        status = _configuration(
            ActionStatusConfiguration, data.get('status_key'),
            'Action status', row.status_key,
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if status.internal_key == row.status_key:
        return jsonify({'action_item': _serialize_rows([row])[0]})
    old = row.to_dict()
    now = datetime.utcnow()
    row.status_key = status.internal_key
    row.updated_by = request.current_user.id
    if status.internal_key == 'IN_PROGRESS' and not row.started_at:
        row.started_at = now
    if status.internal_key == 'COMPLETED':
        row.completed_at = now
    elif status.internal_key == 'CANCELLED':
        row.cancelled_at = now
    elif status.internal_key == 'EXPIRED':
        row.expired_at = now
    cid = _cid()
    _audit('action_item_status_changed', row, old, row.to_dict(), cid)
    if (
        status.internal_key == 'COMPLETED'
        and row.assigned_by_user_id
        and row.assigned_by_user_id != request.current_user.id
    ):
        notify_action_item(
            row, row.assigned_by_user, 'completed', cid,
            idempotency_key=f'action:{row.id}:completed',
        )
    db.session.commit()
    return jsonify({
        'action_item': _serialize_rows([row])[0],
        'correlation_id': cid,
    })


def _set_active(item_id, active):
    row = _item(item_id, include_inactive=True)
    if not row:
        return jsonify({'error': 'Action Item not found'}), 404
    old = row.to_dict()
    row.is_active = active
    row.archived_at = None if active else datetime.utcnow()
    row.updated_by = request.current_user.id
    cid = _cid()
    _audit(
        'action_item_restored' if active else 'action_item_archived',
        row, old, row.to_dict(), cid,
    )
    db.session.commit()
    return jsonify({
        'action_item': _serialize_rows([row])[0],
        'correlation_id': cid,
    })


@action_items_bp.post('/<int:item_id>/archive')
@require_capability('action_items.archive', 'OWN')
def archive_action_item(item_id):
    return _set_active(item_id, False)


@action_items_bp.post('/<int:item_id>/restore')
@require_capability('action_items.archive', 'OWN')
def restore_action_item(item_id):
    return _set_active(item_id, True)
