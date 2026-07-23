"""Unified tenant-scoped Visit administration APIs."""

from datetime import datetime
import re
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app.middleware import require_capability
from app.models.activity import ActivityLog
from app.models.base import db
from app.models.lead import Lead
from app.models.location import Location, MeetingRoom
from app.models.project import Project
from app.models.user import User
from app.models.visit import (
    Visit, VisitAttachment, VisitParticipant, VisitStatusConfiguration,
    VisitTag, VisitTypeConfiguration,
)
from app.utils.time_utils import parse_business_datetime_to_utc_naive


visits_bp = Blueprint('visits', __name__, url_prefix='/api/visits')

PARTICIPANT_TYPES = {
    'LEAD', 'CHANNEL_PARTNER', 'CUSTOMER', 'USER', 'ORGANISATION', 'OTHER',
}
PRIORITIES = {'LOW', 'NORMAL', 'HIGH', 'URGENT'}
VISIBILITY_VALUES = {'VISIBLE', 'HIDDEN'}
CONFIG_FIELDS = {
    'display_name', 'display_order', 'colour', 'is_active', 'visibility',
}


def _tenant_id():
    return request.current_user.tenant_id or getattr(request, 'current_tenant_id', None)


def _correlation_id():
    return str(request.headers.get('X-Correlation-ID') or uuid4())


def _audit(action, resource_id, old_value, new_value, correlation_id,
           resource_type='Visit'):
    db.session.add(ActivityLog(
        tenant_id=_tenant_id(), user_id=request.current_user.id,
        action=action, module='visits', resource_type=resource_type,
        resource_id=resource_id, old_value=old_value, new_value=new_value,
        correlation_id=correlation_id, ip_address=request.remote_addr,
    ))


def _parse_datetime(value, field):
    if value in (None, ''):
        return None
    try:
        return parse_business_datetime_to_utc_naive(value)
    except ValueError as exc:
        raise ValueError(f'{field} must be an ISO-8601 datetime') from exc


def _visit(visit_id):
    return Visit.query.filter_by(id=visit_id, tenant_id=_tenant_id()).first()


def _validate_reference(model, value, label, required=False, active_only=False):
    if value in (None, ''):
        if required:
            raise ValueError(f'{label} is required')
        return None
    query = model.query.filter_by(id=int(value), tenant_id=_tenant_id())
    if active_only and hasattr(model, 'is_active'):
        query = query.filter_by(is_active=True)
    row = query.first()
    if not row:
        raise ValueError(f'{label} was not found in this tenant')
    return row


def _validate_user(value, label):
    return _validate_reference(User, value, label)


def _validate_configuration(model, internal_key, label, allow_inactive_key=None):
    key = str(internal_key or '').strip().upper()
    row = model.query.filter_by(
        tenant_id=_tenant_id(), internal_key=key
    ).first()
    if not row or (not row.is_active and key != allow_inactive_key):
        raise ValueError(f'{label} is not active for this tenant')
    return key


def _validate_visit_payload(data, current=None):
    location = _validate_reference(
        Location, data.get('location_id', current.location_id if current else None),
        'Location', required=True, active_only=current is None,
    )
    room_value = data.get('meeting_room_id', current.meeting_room_id if current else None)
    room = _validate_reference(MeetingRoom, room_value, 'Meeting room')
    if room and room.location_id != location.id:
        raise ValueError('Meeting room must belong to the visit location')

    project_value = data.get('project_id', current.project_id if current else None)
    lead_value = data.get('lead_id', current.lead_id if current else None)
    assigned_value = data.get('assigned_user_id', current.assigned_user_id if current else None)
    reception_value = data.get(
        'reception_assigned_user_id',
        current.reception_assigned_user_id if current else None,
    )
    escort_value = data.get('escort_user_id', current.escort_user_id if current else None)
    project = _validate_reference(Project, project_value, 'Project')
    lead = _validate_reference(Lead, lead_value, 'Lead')
    assigned = _validate_user(assigned_value, 'Assigned user')
    reception = _validate_user(reception_value, 'Reception user')
    escort = _validate_user(escort_value, 'Escort user')

    visit_type_key = _validate_configuration(
        VisitTypeConfiguration,
        data.get('visit_type_key', current.visit_type_key if current else None),
        'Visit type',
        current.visit_type_key if current else None,
    )
    status_key = _validate_configuration(
        VisitStatusConfiguration,
        data.get('status_key', current.status_key if current else 'SCHEDULED'),
        'Visit status',
        current.status_key if current else None,
    )
    priority = str(data.get('priority', current.priority if current else 'NORMAL')).upper()
    if priority not in PRIORITIES:
        raise ValueError('Invalid visit priority')
    visitor_count = int(data.get(
        'visitor_count', current.visitor_count if current else 1
    ))
    if visitor_count < 1:
        raise ValueError('Visitor count must be positive')

    expected = _parse_datetime(
        data.get('expected_arrival', current.expected_arrival if current else None),
        'Expected arrival',
    )
    check_in = _parse_datetime(
        data.get('actual_check_in', current.actual_check_in if current else None),
        'Actual check-in',
    )
    check_out = _parse_datetime(
        data.get('actual_check_out', current.actual_check_out if current else None),
        'Actual check-out',
    )
    if check_in and check_out and check_out < check_in:
        raise ValueError('Actual check-out cannot be before actual check-in')

    return {
        'location_id': location.id,
        'meeting_room_id': room.id if room else None,
        'project_id': project.id if project else None,
        'lead_id': lead.id if lead else None,
        'assigned_user_id': assigned.id if assigned else None,
        'reception_assigned_user_id': reception.id if reception else None,
        'escort_user_id': escort.id if escort else None,
        'visit_type_key': visit_type_key, 'status_key': status_key,
        'priority': priority, 'visitor_count': visitor_count,
        'expected_arrival': expected, 'actual_check_in': check_in,
        'actual_check_out': check_out,
    }


def _sync_participants(row, values):
    if values is None:
        return
    row.participants[:] = []
    seen = set()
    for value in values:
        participant_type = str(value.get('participant_type') or '').upper()
        if participant_type not in PARTICIPANT_TYPES:
            raise ValueError('Invalid participant type')
        reference_id = value.get('reference_id')
        display_name = str(value.get('display_name') or '').strip() or None
        if participant_type == 'LEAD' and reference_id:
            ref = _validate_reference(Lead, reference_id, 'Participant lead')
            display_name = display_name or ref.name
        elif participant_type == 'USER' and reference_id:
            ref = _validate_user(reference_id, 'Participant user')
            display_name = display_name or ref.name
        elif not reference_id and not display_name:
            raise ValueError('Participant name or reference is required')
        identity = (participant_type, int(reference_id) if reference_id else None, display_name)
        if identity in seen:
            continue
        seen.add(identity)
        row.participants.append(VisitParticipant(
            tenant_id=_tenant_id(), participant_type=participant_type,
            reference_id=int(reference_id) if reference_id else None,
            display_name=display_name, is_primary=bool(value.get('is_primary')),
            participant_metadata=value.get('participant_metadata') or {},
        ))


def _sync_tags(row, values):
    if values is None:
        return
    tags = []
    for value in values:
        tag = str(value or '').strip()
        if tag and tag.lower() not in {item.lower() for item in tags}:
            tags.append(tag[:80])
    row.tags[:] = [VisitTag(tenant_id=_tenant_id(), tag=tag) for tag in tags]


def _sync_attachments(row, values):
    if values is None:
        return
    row.attachments[:] = []
    for value in values:
        file_name = str(value.get('file_name') or '').strip()
        storage_reference = str(value.get('storage_reference') or '').strip()
        if not file_name or not storage_reference:
            raise ValueError('Attachment file name and storage reference are required')
        row.attachments.append(VisitAttachment(
            tenant_id=_tenant_id(), file_name=file_name,
            mime_type=value.get('mime_type'), storage_reference=storage_reference,
            attachment_metadata=value.get('attachment_metadata') or {},
            created_by=request.current_user.id,
        ))


def _apply_visit_fields(row, data, validated):
    for key, value in validated.items():
        setattr(row, key, value)
    for field in (
        'purpose', 'notes', 'source', 'operational_metadata', 'token_code',
    ):
        if field in data:
            setattr(row, field, data[field])
    _sync_participants(row, data.get('participants') if 'participants' in data else None)
    _sync_tags(row, data.get('tags') if 'tags' in data else None)
    _sync_attachments(row, data.get('attachments') if 'attachments' in data else None)


@visits_bp.get('/configuration')
@require_capability('visits.view', 'TENANT')
def list_visit_configuration():
    types = VisitTypeConfiguration.query.filter_by(tenant_id=_tenant_id()).order_by(
        VisitTypeConfiguration.display_order, VisitTypeConfiguration.id
    ).all()
    statuses = VisitStatusConfiguration.query.filter_by(tenant_id=_tenant_id()).order_by(
        VisitStatusConfiguration.display_order, VisitStatusConfiguration.id
    ).all()
    return jsonify({
        'visit_types': [row.to_dict() for row in types],
        'visit_statuses': [row.to_dict() for row in statuses],
    })


def _update_configuration(model, internal_key, resource_type):
    key = str(internal_key or '').upper()
    row = model.query.filter_by(tenant_id=_tenant_id(), internal_key=key).first()
    if not row:
        return jsonify({'error': 'Visit configuration not found'}), 404
    data = request.get_json() or {}
    if data.get('visibility') and data['visibility'] not in VISIBILITY_VALUES:
        return jsonify({'error': 'Invalid visibility'}), 400
    if 'display_name' in data and not str(data['display_name'] or '').strip():
        return jsonify({'error': 'Display name is required'}), 400
    old = row.to_dict()
    for field in CONFIG_FIELDS | ({'is_terminal'} if model is VisitStatusConfiguration else set()):
        if field in data:
            setattr(row, field, data[field])
    row.updated_by = request.current_user.id
    correlation_id = _correlation_id()
    _audit('visit_configuration_updated', row.id, old, row.to_dict(),
           correlation_id, resource_type=resource_type)
    db.session.commit()
    return jsonify({'configuration': row.to_dict(), 'correlation_id': correlation_id})


def _create_configuration(model, resource_type):
    data = request.get_json() or {}
    key = str(data.get('internal_key') or '').strip().upper()
    name = str(data.get('display_name') or '').strip()
    if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', key) or not name:
        return jsonify({
            'error': 'Internal key and display name are required; key must use uppercase letters, numbers and underscores',
        }), 400
    if model.query.filter_by(tenant_id=_tenant_id(), internal_key=key).first():
        return jsonify({'error': 'Visit configuration key already exists'}), 409
    visibility = str(data.get('visibility') or 'VISIBLE').upper()
    if visibility not in VISIBILITY_VALUES:
        return jsonify({'error': 'Invalid visibility'}), 400
    row = model(
        tenant_id=_tenant_id(), internal_key=key, display_name=name,
        display_order=int(data.get('display_order') or 0),
        colour=data.get('colour') or '#64748b',
        is_active=bool(data.get('is_active', True)),
        visibility=visibility,
        updated_by=request.current_user.id,
    )
    if isinstance(row, VisitStatusConfiguration):
        row.is_terminal = bool(data.get('is_terminal', False))
    db.session.add(row)
    db.session.flush()
    correlation_id = _correlation_id()
    _audit('visit_configuration_created', row.id, None, row.to_dict(),
           correlation_id, resource_type=resource_type)
    db.session.commit()
    return jsonify({'configuration': row.to_dict(), 'correlation_id': correlation_id}), 201


@visits_bp.post('/configuration/types')
@require_capability('visits.manage', 'TENANT')
def create_visit_type():
    return _create_configuration(VisitTypeConfiguration, 'VisitTypeConfiguration')


@visits_bp.post('/configuration/statuses')
@require_capability('visits.manage', 'TENANT')
def create_visit_status():
    return _create_configuration(VisitStatusConfiguration, 'VisitStatusConfiguration')


@visits_bp.put('/configuration/types/<string:internal_key>')
@require_capability('visits.manage', 'TENANT')
def update_visit_type(internal_key):
    return _update_configuration(VisitTypeConfiguration, internal_key, 'VisitTypeConfiguration')


@visits_bp.put('/configuration/statuses/<string:internal_key>')
@require_capability('visits.manage', 'TENANT')
def update_visit_status(internal_key):
    return _update_configuration(VisitStatusConfiguration, internal_key, 'VisitStatusConfiguration')


@visits_bp.get('')
@require_capability('visits.view', 'TENANT')
def list_visits():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 25, type=int)))
    query = Visit.query.filter_by(tenant_id=_tenant_id())
    active = str(request.args.get('active', 'true')).lower()
    if active in ('true', 'false'):
        query = query.filter(Visit.is_active == (active == 'true'))
    for argument, column in (
        ('status', Visit.status_key), ('type', Visit.visit_type_key),
        ('location_id', Visit.location_id), ('project_id', Visit.project_id),
        ('assigned_user_id', Visit.assigned_user_id), ('lead_id', Visit.lead_id),
    ):
        value = request.args.get(argument)
        if value not in (None, ''):
            try:
                parsed = int(value) if argument.endswith('_id') else value.upper()
            except ValueError:
                return jsonify({'error': f'{argument} must be numeric'}), 400
            query = query.filter(column == parsed)
    try:
        date_from = _parse_datetime(request.args.get('date_from'), 'Date from')
        date_to = _parse_datetime(request.args.get('date_to'), 'Date to')
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    if date_from:
        query = query.filter(Visit.expected_arrival >= date_from)
    if date_to:
        query = query.filter(Visit.expected_arrival <= date_to)
    search = str(request.args.get('search') or '').strip()
    if search:
        like = f'%{search}%'
        query = query.outerjoin(Lead, Lead.id == Visit.lead_id).filter(or_(
            Visit.purpose.ilike(like), Visit.source.ilike(like), Lead.name.ilike(like),
        ))
    total = query.count()
    rows = query.order_by(
        Visit.expected_arrival.desc().nullslast(), Visit.id.desc()
    ).offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'visits': [row.to_dict(include_details=False) for row in rows],
        'pagination': {'page': page, 'per_page': per_page, 'total': total},
    })


@visits_bp.post('')
@require_capability('visits.manage', 'TENANT')
def create_visit():
    data = request.get_json() or {}
    try:
        validated = _validate_visit_payload(data)
        row = Visit(
            tenant_id=_tenant_id(), created_by=request.current_user.id,
            updated_by=request.current_user.id,
        )
        _apply_visit_fields(row, data, validated)
        db.session.add(row)
        db.session.flush()
        correlation_id = _correlation_id()
        _audit('visit_created', row.id, None, row.to_dict(), correlation_id)
        db.session.commit()
        return jsonify({'visit': row.to_dict(), 'correlation_id': correlation_id}), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


@visits_bp.get('/<int:visit_id>')
@require_capability('visits.view', 'TENANT')
def get_visit(visit_id):
    row = _visit(visit_id)
    if not row:
        return jsonify({'error': 'Visit not found'}), 404
    return jsonify({'visit': row.to_dict()})


@visits_bp.put('/<int:visit_id>')
@require_capability('visits.manage', 'TENANT')
def update_visit(visit_id):
    row = _visit(visit_id)
    if not row:
        return jsonify({'error': 'Visit not found'}), 404
    data = request.get_json() or {}
    old = row.to_dict()
    old_status = row.status_key
    try:
        validated = _validate_visit_payload(data, current=row)
        _apply_visit_fields(row, data, validated)
        row.updated_by = request.current_user.id
        db.session.flush()
        correlation_id = _correlation_id()
        action = 'visit_lifecycle_changed' if row.status_key != old_status else 'visit_updated'
        _audit(action, row.id, old, row.to_dict(), correlation_id)
        db.session.commit()
        return jsonify({'visit': row.to_dict(), 'correlation_id': correlation_id})
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


def _set_active(visit_id, active):
    row = _visit(visit_id)
    if not row:
        return jsonify({'error': 'Visit not found'}), 404
    old = row.to_dict()
    row.is_active = active
    row.archived_at = None if active else datetime.utcnow()
    row.updated_by = request.current_user.id
    correlation_id = _correlation_id()
    _audit('visit_restored' if active else 'visit_archived',
           row.id, old, row.to_dict(), correlation_id)
    db.session.commit()
    return jsonify({'visit': row.to_dict(), 'correlation_id': correlation_id})


@visits_bp.post('/<int:visit_id>/archive')
@require_capability('visits.manage', 'TENANT')
def archive_visit(visit_id):
    return _set_active(visit_id, False)


@visits_bp.post('/<int:visit_id>/restore')
@require_capability('visits.manage', 'TENANT')
def restore_visit(visit_id):
    return _set_active(visit_id, True)
