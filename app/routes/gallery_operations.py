"""Visit-driven Gallery Operations and Reception APIs."""

import logging
from datetime import date, datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import joinedload, selectinload

from app.middleware import require_capability
from app.models.activity import ActivityLog
from app.models.base import db
from app.models.channel_partner import ChannelPartner
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
from app.services.channel_partner_events import notify_channel_partner_visit
from app.services.visit_builder import (
    create_lead_row, default_visit_assigned_user, find_duplicate_lead_by_phone,
    sync_lead_owner_if_unset,
)
from app.services.pipeline_engine import transition_lead
from app.utils.time_utils import business_date_bounds_utc_naive, now_ist

logger = logging.getLogger(__name__)


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


def _base_visit_query():
    query = Visit.query.options(
        joinedload(Visit.location), joinedload(Visit.meeting_room),
        joinedload(Visit.project), joinedload(Visit.lead),
        joinedload(Visit.assigned_user), selectinload(Visit.participants),
    ).filter_by(tenant_id=_tenant_id(), is_active=True)
    return _location_filter(query)


def _view_query(view, start, end):
    query = _base_visit_query()
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
        tenant_id=_tenant_id(), is_active=True
    ).order_by(Project.name).limit(500).all()
    channel_partners = ChannelPartner.query.filter_by(
        tenant_id=_tenant_id(), is_active=True
    ).order_by(ChannelPartner.name).limit(500).all()
    return jsonify({
        'locations': [{'id': row.id, 'name': row.name} for row in locations],
        'meeting_rooms': [
            {'id': row.id, 'name': row.name, 'location_id': row.location_id}
            for row in rooms
        ],
        'users': [{'id': row.id, 'name': row.name, 'role': row.role} for row in users],
        'projects': [{'id': row.id, 'name': row.name} for row in projects],
        'channel_partners': [
            {'id': row.id, 'name': row.name} for row in channel_partners
        ],
    })


def _mask_phone(phone):
    value = str(phone or '').strip()
    if len(value) <= 4:
        return value
    return '*' * (len(value) - 4) + value[-4:]


@gallery_operations_bp.get('/lead-lookup')
@require_capability('gallery.check_in', 'TENANT')
def lead_lookup():
    """Search existing Leads for the walk-in/visit-planning "find existing
    lead" flows. Deliberately NOT the same query as GET /api/leads: that
    endpoint applies apply_valid_lead_capture_scope, a "countable lead"
    business-quality filter meant for the Leads dashboard, which can hide a
    perfectly real Lead from this lookup (e.g. a lead the duplicate-phone
    check on Lead creation would still find). Reception needs to find any
    active Lead in the tenant by name/phone/email, tenant-scoped only.
    Phone is returned masked - this lookup is a visual pick-list, not a
    place to expose full contact numbers to whoever is on Reception duty.
    """
    search = str(request.args.get('search') or '').strip()
    if len(search) < 2:
        return jsonify({'leads': []})
    limit = min(10, max(1, request.args.get('limit', 8, type=int)))
    like = f'%{search}%'
    rows = Lead.query.options(
        joinedload(Lead.project), joinedload(Lead.channel_partner),
    ).filter(
        Lead.tenant_id == _tenant_id(), Lead.is_active == True,
        or_(Lead.name.ilike(like), Lead.phone.ilike(like), Lead.email.ilike(like)),
    ).order_by(Lead.created_at.desc()).limit(limit).all()
    return jsonify({'leads': [
        {
            'id': row.id, 'name': row.name,
            'phone_masked': _mask_phone(row.phone),
            'status': row.status,
            'project_id': row.project_id,
            'project_name': row.project.name if row.project else None,
            'channel_partner_id': row.channel_partner_id,
            'channel_partner_name': row.channel_partner.name if row.channel_partner else None,
        }
        for row in rows
    ]})


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
    search = str(request.args.get('search') or '').strip()
    try:
        if search:
            # A search term is looking for one specific record across the
            # tenant, not browsing the currently selected tab - status/date
            # scoping would otherwise hide results that legitimately match
            # (e.g. a visit that already completed, or one on another day).
            query = _base_visit_query()
        else:
            start, end = _business_bounds()
            query = _view_query(view, start, end)
    except (TypeError, ValueError) as exc:
        return jsonify({'error': str(exc)}), 400
    if search:
        like = f'%{search}%'
        query = query.outerjoin(Lead, Lead.id == Visit.lead_id).filter(or_(
            Visit.purpose.ilike(like), Visit.source.ilike(like),
            Lead.name.ilike(like), Lead.phone.ilike(like),
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
        new_lead_data = data.get('new_lead') if not lead else None
        new_lead_created = False
        if new_lead_data:
            new_lead_name = str(new_lead_data.get('name') or '').strip()
            new_lead_phone = str(new_lead_data.get('phone') or '').strip()
            new_lead_email = str(new_lead_data.get('email') or '').strip()
            if not new_lead_name:
                raise ValueError('New lead name is required')
            if not new_lead_phone and not new_lead_email:
                raise ValueError('At least one contact method is required for a new lead')
            force = bool(new_lead_data.get('force')) and request.current_user.role == 'superadmin'
            duplicate = find_duplicate_lead_by_phone(_tenant_id(), new_lead_phone, force=force)
            if duplicate:
                return jsonify({
                    'error': 'duplicate_phone',
                    'message': 'A lead with this phone number already exists.',
                    'existing_lead': {
                        'id': duplicate.id, 'name': duplicate.name,
                        'phone': duplicate.phone, 'status': duplicate.status,
                    },
                }), 409
            lead = create_lead_row(
                _tenant_id(), request.current_user, new_lead_name,
                phone=new_lead_phone or None,
                alternate_phone=str(new_lead_data.get('alternate_phone') or '').strip() or None,
                email=new_lead_email or None,
                source=str(new_lead_data.get('source') or '').strip() or 'Walk-in',
                project_id=data.get('project_id'),
            )
            db.session.add(lead)
            db.session.flush()
            new_lead_created = True
        project = _reference(Project, data.get('project_id'), 'Project')
        assigned_user_id_value = (
            default_visit_assigned_user(lead, data.get('assigned_user_id'))
            if lead else data.get('assigned_user_id')
        )
        assigned = _reference(User, assigned_user_id_value, 'Assigned user')
        if assigned and not assigned.is_active:
            raise ValueError('Assigned user is inactive')
        if lead and assigned:
            sync_lead_owner_if_unset(lead, assigned)
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
        participant_reference_id = participant.get('reference_id')
        participant_partner = None
        if category == 'CHANNEL_PARTNER' and participant_reference_id:
            participant_partner = _reference(
                ChannelPartner, participant_reference_id,
                'Channel Partner', active_only=True,
            )
            if not participant_partner:
                raise ValueError('Channel Partner is required')
            display_name = participant_partner.name
        # Unregistered Channel Partner: no reference_id given, fall through to
        # the same free-text display_name path OTHER/VENDOR already use;
        # 'A lead or visitor name is required' below enforces display_name.
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
            participant_metadata = {'reception_category': category or 'OTHER'}
            if category == 'CHANNEL_PARTNER' and not participant_partner:
                participant_metadata['unregistered'] = True
            row.participants.append(VisitParticipant(
                tenant_id=_tenant_id(), participant_type=stored_type,
                reference_id=(
                    participant_partner.id if participant_partner else None
                ),
                display_name=display_name, is_primary=True,
                participant_metadata=participant_metadata,
            ))
        db.session.add(row)
        db.session.flush()
        correlation_id = _correlation_id()
        if new_lead_created:
            db.session.add(ActivityLog(
                tenant_id=_tenant_id(), user_id=request.current_user.id,
                action='lead_created_from_walk_in', module='gallery_operations',
                resource_type='Lead', resource_id=lead.id,
                old_value=None, new_value=lead.to_dict(),
                correlation_id=correlation_id, ip_address=request.remote_addr,
            ))
        _audit('gallery_walk_in_created', row, None, correlation_id)
        if assigned:
            _notify_assignment(row, assigned, correlation_id)
        if participant_partner:
            notify_channel_partner_visit(
                row, 'visit_arrival', correlation_id
            )
        db.session.commit()
        response = {'visit': row.to_dict(), 'correlation_id': correlation_id}
        if new_lead_created:
            response['lead'] = lead.to_dict()
        return jsonify(response), 201
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
        if target == 'CHECKED_IN':
            notify_channel_partner_visit(
                row, 'visit_arrival', correlation_id
            )
        elif target == 'COMPLETED':
            notify_channel_partner_visit(
                row, 'visit_completed', correlation_id
            )
            if row.lead_id and row.lead:
                # A completed physical visit is real-world evidence the
                # Lead should advance to site_visit_done. Best-effort: the
                # pipeline engine's own rules decide whether that's actually
                # a valid move from the Lead's current stage (e.g. it's a
                # no-op if already past that stage); checkout itself must
                # never fail because of this.
                try:
                    transition_lead(
                        row.lead, 'site_visit_done', actor=request.current_user,
                        source='GALLERY_CHECKOUT', reason='Visit checked out',
                        context={}, visit=row, correlation_id=correlation_id,
                    )
                except Exception:
                    # Best-effort only - an invalid/blocked transition (or
                    # any unexpected error in this secondary nudge) must
                    # never roll back a real physical checkout.
                    logger.exception(
                        'gallery checkout: pipeline transition to '
                        'site_visit_done failed for lead %s', row.lead_id,
                    )
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
        if row.lead_id:
            sync_lead_owner_if_unset(row.lead, user)
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
