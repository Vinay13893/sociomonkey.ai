"""Platform location and lightweight meeting-room administration."""

from datetime import datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app.middleware import require_capability
from app.models.activity import ActivityLog
from app.models.base import db
from app.models.location import Location, MeetingRoom, ProjectLocation, TenantBrand
from app.models.project import Project


locations_bp = Blueprint('locations', __name__, url_prefix='/api/locations')
LOCATION_TYPES = {
    'HEAD_OFFICE', 'SALES_GALLERY', 'PROJECT_SITE', 'SITE_OFFICE',
    'TEMPORARY_OFFICE', 'EXTERNAL_LOCATION', 'OTHER',
}
ROOM_STATUSES = {'AVAILABLE', 'OCCUPIED', 'RESERVED', 'MAINTENANCE', 'OUT_OF_SERVICE'}
RELATIONSHIP_TYPES = {'SERVES', 'HEAD_OFFICE', 'SALES_GALLERY', 'SITE_OFFICE', 'PROJECT_SITE'}


def _tenant_id():
    return request.current_user.tenant_id or getattr(request, 'current_tenant_id', None)


def _cid():
    return str(request.headers.get('X-Correlation-ID') or uuid4())


def _audit(action, resource_type, resource_id, old, new, cid):
    db.session.add(ActivityLog(
        tenant_id=_tenant_id(), user_id=request.current_user.id, action=action,
        module='locations', resource_type=resource_type, resource_id=resource_id,
        old_value=old, new_value=new, correlation_id=cid, ip_address=request.remote_addr,
    ))


def _page_args():
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(100, max(1, request.args.get('per_page', 25, type=int)))
    return page, per_page


def _location(location_id):
    return Location.query.filter_by(id=location_id, tenant_id=_tenant_id()).first()


def _sync_projects(location, project_ids, relationship_type='SERVES'):
    relationship_type = str(relationship_type or 'SERVES').upper()
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError('Invalid project relationship type')
    ids = sorted({int(value) for value in (project_ids or [])})
    if ids:
        count = Project.query.filter(
            Project.tenant_id == _tenant_id(), Project.id.in_(ids)
        ).count()
        if count != len(ids):
            raise ValueError('One or more projects are not in this tenant')
    ProjectLocation.query.filter_by(
        tenant_id=_tenant_id(), location_id=location.id
    ).delete(synchronize_session=False)
    for project_id in ids:
        db.session.add(ProjectLocation(
            tenant_id=_tenant_id(), project_id=project_id,
            location_id=location.id, relationship_type=relationship_type,
        ))


@locations_bp.get('/brands')
@require_capability('locations.view', 'TENANT')
def list_brands():
    rows = TenantBrand.query.filter_by(tenant_id=_tenant_id(), is_active=True).order_by(TenantBrand.name).all()
    return jsonify({'brands': [row.to_dict() for row in rows]})


@locations_bp.get('')
@require_capability('locations.view', 'TENANT')
def list_locations():
    page, per_page = _page_args()
    query = Location.query.filter_by(tenant_id=_tenant_id())
    active = request.args.get('active', 'true').lower()
    if active in ('true', 'false'):
        query = query.filter(Location.is_active == (active == 'true'))
    location_type = request.args.get('type')
    if location_type:
        query = query.filter(Location.location_type == location_type.upper())
    search = str(request.args.get('search') or '').strip()
    if search:
        like = f'%{search}%'
        query = query.filter(or_(Location.name.ilike(like), Location.code.ilike(like),
                                 Location.city.ilike(like), Location.state.ilike(like)))
    total = query.count()
    rows = query.order_by(Location.name, Location.id).offset((page-1)*per_page).limit(per_page).all()
    return jsonify({'locations':[row.to_dict() for row in rows],
                    'pagination':{'page':page,'per_page':per_page,'total':total}})


@locations_bp.post('')
@require_capability('locations.manage', 'TENANT')
def create_location():
    data = request.get_json() or {}
    code = str(data.get('code') or '').strip().upper()
    name = str(data.get('name') or '').strip()
    location_type = str(data.get('location_type') or '').strip().upper()
    if not code or not name or location_type not in LOCATION_TYPES:
        return jsonify({'error':'Name, code and valid location type are required'}), 400
    if Location.query.filter_by(tenant_id=_tenant_id(), code=code).first():
        return jsonify({'error':'Location code already exists'}), 409
    brand_id = data.get('brand_id')
    if brand_id and not TenantBrand.query.filter_by(id=brand_id, tenant_id=_tenant_id()).first():
        return jsonify({'error':'Brand not found in tenant'}), 400
    row = Location(
        tenant_id=_tenant_id(), code=code, name=name, location_type=location_type,
        brand_id=brand_id, created_by=request.current_user.id, updated_by=request.current_user.id,
    )
    for field in ('address_line_1','address_line_2','city','state','country','postal_code',
                  'latitude','longitude','contact_details','working_hours','notes'):
        if field in data:
            setattr(row, field, data[field])
    db.session.add(row)
    db.session.flush()
    try:
        _sync_projects(row, data.get('project_ids', []), data.get('project_relationship_type'))
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error':str(exc)}), 400
    db.session.flush()
    db.session.expire(row, ['project_links'])
    cid = _cid()
    _audit('location_created','Location',row.id,None,row.to_dict(),cid)
    db.session.commit()
    return jsonify({'location':row.to_dict(),'correlation_id':cid}), 201


@locations_bp.put('/<int:location_id>')
@require_capability('locations.manage', 'TENANT')
def update_location(location_id):
    row = _location(location_id)
    if not row:
        return jsonify({'error':'Location not found'}), 404
    data = request.get_json() or {}
    old = row.to_dict()
    if 'code' in data and str(data['code']).strip().upper() != row.code:
        code = str(data['code']).strip().upper()
        if not code or Location.query.filter_by(tenant_id=_tenant_id(), code=code).first():
            return jsonify({'error':'Location code is invalid or already exists'}), 409
        row.code = code
    if 'location_type' in data and str(data['location_type']).upper() not in LOCATION_TYPES:
        return jsonify({'error':'Invalid location type'}), 400
    if data.get('brand_id') and not TenantBrand.query.filter_by(
        id=data['brand_id'], tenant_id=_tenant_id()
    ).first():
        return jsonify({'error':'Brand not found in tenant'}), 400
    for field in ('name','location_type','brand_id','address_line_1','address_line_2','city',
                  'state','country','postal_code','latitude','longitude','contact_details',
                  'working_hours','notes'):
        if field in data:
            setattr(row, field, str(data[field]).upper() if field == 'location_type' else data[field])
    row.updated_by = request.current_user.id
    try:
        if 'project_ids' in data:
            _sync_projects(row, data['project_ids'], data.get('project_relationship_type'))
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({'error':str(exc)}), 400
    db.session.flush()
    db.session.expire(row, ['project_links'])
    cid = _cid()
    _audit('location_updated','Location',row.id,old,row.to_dict(),cid)
    db.session.commit()
    return jsonify({'location':row.to_dict(),'correlation_id':cid})


def _set_location_active(location_id, active):
    row = _location(location_id)
    if not row:
        return jsonify({'error':'Location not found'}), 404
    old = row.to_dict()
    row.is_active = active
    row.archived_at = None if active else datetime.utcnow()
    row.updated_by = request.current_user.id
    cid = _cid()
    _audit('location_restored' if active else 'location_archived','Location',row.id,old,row.to_dict(),cid)
    db.session.commit()
    return jsonify({'location':row.to_dict(),'correlation_id':cid})


@locations_bp.post('/<int:location_id>/archive')
@require_capability('locations.manage', 'TENANT')
def archive_location(location_id):
    return _set_location_active(location_id, False)


@locations_bp.post('/<int:location_id>/restore')
@require_capability('locations.manage', 'TENANT')
def restore_location(location_id):
    return _set_location_active(location_id, True)


@locations_bp.get('/meeting-rooms')
@require_capability('meeting_rooms.view', 'TENANT')
def list_rooms():
    page, per_page = _page_args()
    query = MeetingRoom.query.filter_by(tenant_id=_tenant_id())
    if request.args.get('location_id', type=int):
        query = query.filter(MeetingRoom.location_id == request.args.get('location_id', type=int))
    if request.args.get('status'):
        query = query.filter(MeetingRoom.status == request.args['status'].upper())
    active = request.args.get('active', 'true').lower()
    if active in ('true','false'):
        query = query.filter(MeetingRoom.is_active == (active == 'true'))
    search = str(request.args.get('search') or '').strip()
    if search:
        query = query.filter(MeetingRoom.name.ilike(f'%{search}%'))
    total = query.count()
    rows = query.order_by(MeetingRoom.name, MeetingRoom.id).offset((page-1)*per_page).limit(per_page).all()
    return jsonify({'meeting_rooms':[row.to_dict() for row in rows],
                    'pagination':{'page':page,'per_page':per_page,'total':total}})


@locations_bp.post('/meeting-rooms')
@require_capability('meeting_rooms.manage', 'TENANT')
def create_room():
    data = request.get_json() or {}
    location = _location(data.get('location_id'))
    status = str(data.get('status') or 'AVAILABLE').upper()
    name = str(data.get('name') or '').strip()
    if not location or not name or status not in ROOM_STATUSES:
        return jsonify({'error':'Valid location, name and status are required'}), 400
    row = MeetingRoom(
        tenant_id=_tenant_id(), location_id=location.id, name=name,
        code=data.get('code'), capacity=data.get('capacity',1),
        room_type=data.get('room_type') or 'MEETING_ROOM', status=status,
        notes=data.get('notes'), created_by=request.current_user.id,
        updated_by=request.current_user.id,
    )
    db.session.add(row)
    try:
        db.session.flush()
    except Exception:
        db.session.rollback()
        return jsonify({'error':'Room name already exists at this location'}), 409
    cid = _cid()
    _audit('meeting_room_created','MeetingRoom',row.id,None,row.to_dict(),cid)
    db.session.commit()
    return jsonify({'meeting_room':row.to_dict(),'correlation_id':cid}), 201


@locations_bp.put('/meeting-rooms/<int:room_id>')
@require_capability('meeting_rooms.manage', 'TENANT')
def update_room(room_id):
    row = MeetingRoom.query.filter_by(id=room_id, tenant_id=_tenant_id()).first()
    if not row:
        return jsonify({'error':'Meeting room not found'}), 404
    data = request.get_json() or {}
    old = row.to_dict()
    if 'location_id' in data and not _location(data['location_id']):
        return jsonify({'error':'Location not found in tenant'}), 400
    if 'status' in data and str(data['status']).upper() not in ROOM_STATUSES:
        return jsonify({'error':'Invalid room status'}), 400
    for field in ('location_id','name','code','capacity','room_type','status','notes'):
        if field in data:
            setattr(row, field, str(data[field]).upper() if field == 'status' else data[field])
    if not row.name or not row.capacity or int(row.capacity) < 1:
        return jsonify({'error':'Name and positive capacity are required'}), 400
    row.updated_by = request.current_user.id
    cid = _cid()
    _audit('meeting_room_updated','MeetingRoom',row.id,old,row.to_dict(),cid)
    db.session.commit()
    return jsonify({'meeting_room':row.to_dict(),'correlation_id':cid})


def _set_room_active(room_id, active):
    row = MeetingRoom.query.filter_by(id=room_id, tenant_id=_tenant_id()).first()
    if not row:
        return jsonify({'error':'Meeting room not found'}), 404
    old = row.to_dict()
    row.is_active = active
    row.archived_at = None if active else datetime.utcnow()
    row.updated_by = request.current_user.id
    cid = _cid()
    _audit('meeting_room_restored' if active else 'meeting_room_archived',
           'MeetingRoom',row.id,old,row.to_dict(),cid)
    db.session.commit()
    return jsonify({'meeting_room':row.to_dict(),'correlation_id':cid})


@locations_bp.post('/meeting-rooms/<int:room_id>/archive')
@require_capability('meeting_rooms.manage', 'TENANT')
def archive_room(room_id):
    return _set_room_active(room_id, False)


@locations_bp.post('/meeting-rooms/<int:room_id>/restore')
@require_capability('meeting_rooms.manage', 'TENANT')
def restore_room(room_id):
    return _set_room_active(room_id, True)
