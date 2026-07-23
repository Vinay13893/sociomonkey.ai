"""Visit-driven Gallery Operations and Reception APIs."""

from datetime import date, datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import joinedload, selectinload

from app.middleware import require_capability
from app.models.activity import ActivityLog
from app.models.base import db
from app.models.lead import Lead
from app.models.location import Location, MeetingRoom
from app.models.project import Project
from app.models.user import User
from app.models.visit import (
    Visit, VisitParticipant, VisitStatusConfiguration,
    VisitTypeConfiguration,
)
from app.services.notification_events import enqueue_visit_assignment
from app.services.reminder_scheduler import push_notification
from app.utils.time_utils import business_date_bounds_utc_naive, now_ist


gallery_operations_bp = Blueprint(
    'gallery_operations', __name__, url_prefix='/api/gallery-operations'
)

QUEUE_STATUSES = {'WAITING', 'CALLED', 'IN_MEETING'}
INSIDE_STATUSES = {'CHECKED_IN', 'WAITING', 'CALLED', 'IN_MEETING', 'IN_PROGRESS'}
CHECK_OUT_STATUSES = INSIDE_STATUSES
WALK_IN_PARTICIPANT_TYPES = {
    'LEAD', 'CHANNEL_PARTNER', 'CUSTOMER', 'USER', 'ORGANISATION', 'OTHER',
    'INTERNAL_VISITOR', 'VENDOR',
}
LIST_VIEWS = {
    'expected', 'arrived', 'waiting', 'inside', 'completed', 'no_show', 'walk_ins',
}


def _tenant_id():
    return request.current_user.tenant_id or getattr(request, 'current_tenant_id', None)


def _correlation_id():
    return str(request.headers.get('X-Correlation-ID') or uuid4())


def _audit(action, row, old_value, correlation_id):
    db.session.add(ActivityLog(
        tenant_id=_tenant_id(), user_id=request.current_user.id,
        action=action, module='gallery_operations',
        resource_type='Visit', resource_id=row.id,
        old_value=old_value, new_value=row.to_dict(),
        correlation_id=correlation_id, ip_address=request.remote_addr,
    ))


def _visit(visit_id):
    return Visit.query.filter_by(
        id=visit_id, tenant_id=_tenant_id(), is_active=True
    ).first()


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


def _active_configuration(model, internal_key, label):
    row = model.query.filter_by(
        tenant_id=_tenant_id(), internal_key=internal_key, is_active=True
    ).first()
    if not row:
        raise ValueError(f'{label} is not active for this tenant')
    return row


def _business_bounds():
    raw = str(request.args.get('date') or '').strip()
    try:
        selected = date.fromisoformat(raw) if raw else None
    except ValueError as exc:
        raise ValueError('date must use YYYY-MM-DD') from exc
    return business_date_bounds_utc_naive(selected)


def _business_date_label():
    raw = str(request.args.get('date') or '').strip()
    return raw or now_ist().date().isoformat()


def _location_filter(query):
    value = request.args.get('location_id')
    if value in (None, ''):
        return query
    try:
        location_id = int(value)
    except ValueError as exc:
        raise ValueError('location_id must be numeric') from exc
    _reference(Location, location_id, 'Location', active_only=True)
    return query.filter(Visit.location_id == location_id)


def _notify_assignment(row, user, correlation_id):
    push_notification(user.id, {
        'tenant_id': _tenant_id(),
        'type': 'visit_assignment',
        'kind': 'info',
        'title': 'Visit Assigned',
        'message': row.purpose or 'A gallery visit has been assigned to you.',
        'source': 'gallery_operations',
        'visit_id': row.id,
        'location_id': row.location_id,
        'correlation_id': correlation_id,
    })
    enqueue_visit_assignment(
        user, row, correlation_id=correlation_id,
        idempotency_key=(
            f'visit:{row.id}:assignment:{user.id}:{correlation_id}'
        ),
    )


def _serialize(row):
    data = row.to_dict(include_details=False)
    primary = next((item for item in row.participants if item.is_primary), None)
    data['primary_participant'] = primary.display_name if primary else None
    data['participant_count'] = len(row.participants)
    return data


def _view_query(view, start, end):
    query = Visit.query.options(
        joinedload(Visit.location), joinedload(Visit.meeting_room),
        joinedload(Visit.project), joinedload(Visit.lead),
        joinedload(Visit.assigned_user), selectinload(Visit.participants),
    ).filter_by(tenant_id=_tenant_id(), is_active=True)
    query = _location_filter(query)
    if view == 'expected':
        return query.filter(
            Visit.status_key == 'SCHEDULED',
            Visit.expected_arrival >= start, Visit.expected_arrival < end,
        )
    if view == 'arrived':
        return query.filter(
            Visit.status_key == 'CHECKED_IN',
            Visit.actual_check_in >= start, Visit.actual_check_in < end,
        )
    if view == 'waiting':
        return query.filter(
            Visit.status_key.in_(['WAITING', 'CALLED']),
            Visit.actual_check_in >= start, Visit.actual_check_in < end,
        )
    if view == 'inside':
        return query.filter(
            Visit.status_key.in_(['IN_MEETING', 'IN_PROGRESS']),
            Visit.actual_check_in >= start, Visit.actual_check_in < end,
        )
    if view == 'completed':
        return query.filter(
            Visit.status_key == 'COMPLETED',
            Visit.actual_check_out >= start, Visit.actual_check_out < end,
        )
    if view == 'no_show':
        return query.filter(
            Visit.status_key == 'NO_SHOW',
            Visit.expected_arrival >= start, Visit.expected_arrival < end,
        )
    return query.filter(
        Visit.visit_type_key == 'WALK_IN',
        Visit.created_at >= start, Visit.created_at < end,
    )


@gallery_operations_bp.get('/references')
@require_capability('gallery.view', 'TENANT')
def references():
    locations = Location.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    ).order_by(Location.name).limit(250).all()
    rooms = MeetingRoom.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    ).order_by(MeetingRoom.name).limit(500).all()
    users = User.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    ).order_by(User.name).limit(500).all()
    projects = Project.query.filter_by(
        tenant_id=_tenant_id()
    ).order_by(Project.name).limit(500).all()
    return jsonify({
        'locations': [{'id': row.id, 'name': row.name} for row in locations],
        'meeting_rooms': [
            {'id': row.id, 'name': row.name, 'location_id': row.location_id}
            for row in rooms
        ],
        'users': [{'id': row.id, 'name': row.name} for row in users],
        'projects': [{'id': row.id, 'name': row.name} for row in projects],
    })


@gallery_operations_bp.get('/dashboard')
@require_capability('gallery.view', 'TENANT')
def dashboard():
    try:
        start, end = _business_bounds()
        location_id = request.args.get('location_id', type=int)
        filters = [
            Visit.tenant_id == _tenant_id(),
            Visit.is_active.is_(True),
            or_(
                and_(Visit.expected_arrival >= start, Visit.expected_arrival < end),
                and_(Visit.actual_check_in >= start, Visit.actual_check_in < end),
                and_(Visit.actual_check_out >= start, Visit.actual_check_out < end),
                and_(Visit.created_at >= start, Visit.created_at < end),
            ),
        ]
        if location_id:
            _reference(Location, location_id, 'Location', active_only=True)
            filters.append(Visit.location_id == location_id)
        summary = db.session.query(
            func.coalesce(func.sum(case((and_(
                Visit.status_key == 'SCHEDULED',
                Visit.expected_arrival >= start, Visit.expected_arrival < end,
            ), 1), else_=0)), 0).label('expected_today'),
            func.coalesce(func.sum(case((and_(
                Visit.status_key == 'CHECKED_IN',
                Visit.actual_check_in >= start, Visit.actual_check_in < end,
            ), 1), else_=0)), 0).label('checked_in'),
            func.coalesce(func.sum(case((and_(
                Visit.status_key.in_(['WAITING', 'CALLED']),
                Visit.actual_check_in >= start, Visit.actual_check_in < end,
            ), 1), else_=0)), 0).label('waiting'),
            func.coalesce(func.sum(case((and_(
                Visit.status_key.in_(['IN_MEETING', 'IN_PROGRESS']),
                Visit.actual_check_in >= start, Visit.actual_check_in < end,
            ), 1), else_=0)), 0).label('in_meeting'),
            func.coalesce(func.sum(case((and_(
                Visit.status_key == 'COMPLETED',
                Visit.actual_check_out >= start, Visit.actual_check_out < end,
            ), 1), else_=0)), 0).label('completed'),
            func.coalesce(func.sum(case((and_(
                Visit.status_key == 'NO_SHOW',
                Visit.expected_arrival >= start, Visit.expected_arrival < end,
            ), 1), else_=0)), 0).label('no_shows'),
            func.coalesce(func.sum(case((and_(
                Visit.visit_type_key == 'WALK_IN',
                Visit.created_at >= start, Visit.created_at < end,
            ), 1), else_=0)), 0).label('walk_ins'),
        ).filter(*filters).one()
        return jsonify({
            'summary': {
                key: int(getattr(summary, key) or 0)
                for key in (
                    'expected_today', 'checked_in', 'waiting', 'in_meeting',
                    'completed', 'no_shows', 'walk_ins',
                )
            },
            'date': _business_date_label(),
            'timezone': 'Asia/Kolkata',
        })
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400


@gallery_operations_bp.get('/visits')
@require_capability('gallery.view', 'TENANT')
def list_operational_visits():
    view = str(request.args.get('view') or 'expected').lower()
    if view not in LIST_VIEWS:
        return jsonify({'error': 'Invalid reception view'}), 400
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 25, type=int)))
    try:
        start, end = _business_bounds()
        query = _view_query(view, start, end)
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400
    search = str(request.args.get('search') or '').strip()
    if search:
        like = f'%{search}%'
        query = query.outerjoin(Lead, Lead.id == Visit.lead_id).filter(or_(
            Visit.purpose.ilike(like), Visit.source.ilike(like),
            Lead.name.ilike(like),
        ))
    total = query.count()
    rows = query.order_by(
        Visit.expected_arrival.asc().nullslast(), Visit.id.asc()
    ).offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'visits': [_serialize(row) for row in rows],
        'view': view,
        'pagination': {'page': page, 'per_page': per_page, 'total': total},
    })


@gallery_operations_bp.post('/walk-ins')
@require_capability('gallery.check_in', 'TENANT')
def create_walk_in():
    data = request.get_json() or {}
    try:
        location = _reference(
            Location, data.get('location_id'), 'Location', active_only=True
        )
        if not location:
            raise ValueError('Location is required')
        _active_configuration(VisitTypeConfiguration, 'WALK_IN', 'Walk-in visit type')
        _active_configuration(
            VisitStatusConfiguration, 'CHECKED_IN', 'Checked-in visit status'
        )
        lead = _reference(Lead, data.get('lead_id'), 'Lead')
        project = _reference(Project, data.get('project_id'), 'Project')
        assigned = _reference(User, data.get('assigned_user_id'), 'Assigned user')
        if assigned and not assigned.is_active:
            raise ValueError('Assigned user is inactive')
        room = _reference(
            MeetingRoom, data.get('meeting_room_id'), 'Meeting room', active_only=True
        )
        if room and room.location_id != location.id:
            raise ValueError('Meeting room must belong to the visit location')
        participant = data.get('participant') or {}
        category = str(participant.get('type') or '').strip().upper()
        if category and category not in WALK_IN_PARTICIPANT_TYPES:
            raise ValueError('Invalid walk-in participant type')
        display_name = str(participant.get('display_name') or '').strip() or None
        if not lead and not display_name:
            raise ValueError('A lead or visitor name is required')
        priority = str(data.get('priority') or 'NORMAL').upper()
        if priority not in {'LOW', 'NORMAL', 'HIGH', 'URGENT'}:
            raise ValueError('Invalid visit priority')
        now = datetime.utcnow()
        row = Visit(
            tenant_id=_tenant_id(), visit_type_key='WALK_IN',
            status_key='CHECKED_IN', location_id=location.id,
            meeting_room_id=room.id if room else None,
            project_id=project.id if project else None,
            lead_id=lead.id if lead else None,
            assigned_user_id=assigned.id if assigned else None,
            purpose=str(data.get('purpose') or 'Walk-in')[:250],
            notes=data.get('notes'), actual_check_in=now,
            visitor_count=max(1, int(data.get('visitor_count') or 1)),
            source=str(data.get('source') or 'RECEPTION_WALK_IN')[:120],
            priority=priority,
            operational_metadata={
                'arrival_source': str(data.get('arrival_source') or 'WALK_IN'),
            },
            reception_assigned_user_id=request.current_user.id,
            created_by=request.current_user.id, updated_by=request.current_user.id,
        )
        if lead:
            row.participants.append(VisitParticipant(
                tenant_id=_tenant_id(), participant_type='LEAD',
                reference_id=lead.id, display_name=lead.name, is_primary=True,
            ))
        else:
            stored_type = {
                'INTERNAL_VISITOR': 'OTHER', 'VENDOR': 'ORGANISATION',
            }.get(category, category or 'OTHER')
            row.participants.append(VisitParticipant(
                tenant_id=_tenant_id(), participant_type=stored_type,
                display_name=display_name, is_primary=True,
                participant_metadata={'reception_category': category or 'OTHER'},
            ))
        db.session.add(row)
        db.session.flush()
        correlation_id = _correlation_id()
        _audit('gallery_walk_in_created', row, None, correlation_id)
        if assigned:
            _notify_assignment(row, assigned, correlation_id)
        db.session.commit()
        return jsonify({
            'visit': row.to_dict(), 'correlation_id': correlation_id,
        }), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


def _transition(visit_id, target, allowed, action, timestamp_field=None):
    row = _visit(visit_id)
    if not row:
        return jsonify({'error': 'Visit not found'}), 404
    if row.status_key == target:
        return jsonify({'visit': row.to_dict(), 'unchanged': True})
    if row.status_key not in allowed:
        return jsonify({
            'error': f'Visit cannot move from {row.status_key} to {target}',
        }), 409
    try:
        _active_configuration(
            VisitStatusConfiguration, target, f'{target.replace("_", " ").title()} status'
        )
        old = row.to_dict()
        row.status_key = target
        row.updated_by = request.current_user.id
        if timestamp_field:
            setattr(row, timestamp_field, datetime.utcnow())
        if target == 'CHECKED_IN':
            row.reception_assigned_user_id = request.current_user.id
        correlation_id = _correlation_id()
        _audit(action, row, old, correlation_id)
        db.session.commit()
        return jsonify({'visit': row.to_dict(), 'correlation_id': correlation_id})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


@gallery_operations_bp.post('/visits/<int:visit_id>/check-in')
@require_capability('gallery.check_in', 'TENANT')
def check_in(visit_id):
    return _transition(
        visit_id, 'CHECKED_IN', {'SCHEDULED'}, 'gallery_visit_checked_in',
        'actual_check_in',
    )


@gallery_operations_bp.post('/visits/<int:visit_id>/queue-state')
@require_capability('gallery.check_in', 'TENANT')
def change_queue_state(visit_id):
    target = str((request.get_json() or {}).get('status') or '').upper()
    allowed = {
        'WAITING': {'CHECKED_IN', 'CALLED'},
        'CALLED': {'WAITING'},
        'IN_MEETING': {'CHECKED_IN', 'WAITING', 'CALLED'},
    }
    if target not in QUEUE_STATUSES:
        return jsonify({'error': 'Queue status must be WAITING, CALLED or IN_MEETING'}), 400
    return _transition(
        visit_id, target, allowed[target], 'gallery_queue_state_changed'
    )


@gallery_operations_bp.post('/visits/<int:visit_id>/check-out')
@require_capability('gallery.check_out', 'TENANT')
def check_out(visit_id):
    return _transition(
        visit_id, 'COMPLETED', CHECK_OUT_STATUSES,
        'gallery_visit_checked_out', 'actual_check_out',
    )


@gallery_operations_bp.post('/visits/<int:visit_id>/no-show')
@require_capability('gallery.check_out', 'TENANT')
def mark_no_show(visit_id):
    return _transition(
        visit_id, 'NO_SHOW', {'SCHEDULED'}, 'gallery_visit_no_show'
    )


@gallery_operations_bp.put('/visits/<int:visit_id>/assignment')
@require_capability('gallery.assign', 'TENANT')
def assign_visit(visit_id):
    row = _visit(visit_id)
    if not row:
        return jsonify({'error': 'Visit not found'}), 404
    try:
        user = _reference(
            User, (request.get_json() or {}).get('assigned_user_id'), 'Assigned user'
        )
        if not user or not user.is_active:
            raise ValueError('An active assigned user is required')
        old = row.to_dict()
        row.assigned_user_id = user.id
        row.updated_by = request.current_user.id
        correlation_id = _correlation_id()
        _audit('gallery_visit_assigned', row, old, correlation_id)
        _notify_assignment(row, user, correlation_id)
        db.session.commit()
        return jsonify({'visit': row.to_dict(), 'correlation_id': correlation_id})
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


@gallery_operations_bp.put('/visits/<int:visit_id>/room')
@require_capability('gallery.allocate_room', 'TENANT')
def allocate_room(visit_id):
    row = _visit(visit_id)
    if not row:
        return jsonify({'error': 'Visit not found'}), 404
    try:
        room = _reference(
            MeetingRoom, (request.get_json() or {}).get('meeting_room_id'),
            'Meeting room', active_only=True,
        )
        if room and room.location_id != row.location_id:
            raise ValueError('Meeting room must belong to the visit location')
        old = row.to_dict()
        row.meeting_room_id = room.id if room else None
        row.updated_by = request.current_user.id
        correlation_id = _correlation_id()
        _audit('gallery_room_allocation_changed', row, old, correlation_id)
        db.session.commit()
        return jsonify({'visit': row.to_dict(), 'correlation_id': correlation_id})
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 400


@gallery_operations_bp.post('/visits/<int:visit_id>/archive')
@require_capability('gallery.archive', 'TENANT')
def archive_visit(visit_id):
    row = _visit(visit_id)
    if not row:
        return jsonify({'error': 'Visit not found'}), 404
    old = row.to_dict()
    row.is_active = False
    row.archived_at = datetime.utcnow()
    row.updated_by = request.current_user.id
    correlation_id = _correlation_id()
    _audit('gallery_visit_archived', row, old, correlation_id)
    db.session.commit()
    return jsonify({'visit': row.to_dict(), 'correlation_id': correlation_id})
