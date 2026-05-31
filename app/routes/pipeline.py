from flask import Blueprint, jsonify, request

from app import db

from app.middleware import require_auth
from app.models.activity import ActivityLog
from app.models.lead import Lead, StatusHistory
from app.models.user import User
from app.utils.leads import get_user_visible_leads, VALID_STATUSES, STATUS_LABELS

pipeline_bp = Blueprint('pipeline', __name__, url_prefix='/api/pipeline')


@pipeline_bp.route('/stages', methods=['GET'])
@require_auth
def get_pipeline_stages():
    user = request.current_user
    pipeline = {}
    for stage in VALID_STATUSES:
        leads = get_user_visible_leads(user).filter_by(status=stage).all()
        pipeline[stage] = {
            'count': len(leads),
            'leads': [l.to_dict() for l in leads],
        }
    return jsonify({'pipeline': pipeline}), 200


def _can_access_lead(user, lead):
    if not lead or lead.tenant_id != user.tenant_id or not lead.is_active:
        return False
    if user.role == 'team_member':
        return lead.assigned_to == user.id
    if user.role == 'sales_manager':
        team_ids = {u.id for u in User.query.filter_by(manager_id=user.id, is_active=True).all()}
        team_ids.add(user.id)
        return lead.assigned_to in team_ids or lead.sales_manager_id == user.id
    return True


@pipeline_bp.route('/leads/<int:lead_id>/move', methods=['POST'])
@require_auth
def move_pipeline_lead(lead_id):
    user = request.current_user
    data = request.get_json() or {}
    to_status = (data.get('to_status') or '').strip()

    if to_status not in VALID_STATUSES:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(VALID_STATUSES)}'}), 400

    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404
    if not _can_access_lead(user, lead):
        return jsonify({'error': 'Permission denied'}), 403

    old_status = lead.status
    if old_status == to_status:
        return jsonify({
            'lead': lead.to_dict(),
            'message': 'No status change required',
        }), 200

    lead.status = to_status
    db.session.add(StatusHistory(
        lead_id=lead.id,
        old_status=old_status,
        new_status=to_status,
        changed_by=user.id,
    ))

    from_label = STATUS_LABELS.get(old_status, (old_status or '').replace('_', ' ').title())
    to_label = STATUS_LABELS.get(to_status, to_status.replace('_', ' ').title())
    db.session.add(ActivityLog(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action='pipeline_status_change',
        module='pipeline',
        resource_id=lead.id,
        resource_type='Lead',
        old_value={
            'status': old_status,
            'status_label': from_label,
            'source': 'Pipeline Drag & Drop',
        },
        new_value={
            'status': to_status,
            'status_label': to_label,
            'source': 'Pipeline Drag & Drop',
        },
        description=(
            f'Lead Status Changed | From: {from_label} | To: {to_label} | '
            f'Changed By: {user.name} | Source: Pipeline Drag & Drop'
        ),
        ip_address=request.remote_addr,
    ))
    db.session.commit()

    scoped = get_user_visible_leads(user).filter(Lead.status.in_([old_status, to_status])).all()
    stage_counts = {
        old_status: sum(1 for l in scoped if l.status == old_status),
        to_status: sum(1 for l in scoped if l.status == to_status),
    }
    return jsonify({
        'lead': lead.to_dict(),
        'stage_counts': stage_counts,
        'status_change': {
            'from': old_status,
            'to': to_status,
            'source': 'Pipeline Drag & Drop',
        },
    }), 200
