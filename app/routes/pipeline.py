from flask import Blueprint, jsonify, request

from app.middleware import require_auth
from app.models.lead import Lead
from app.utils.leads import get_user_visible_leads, VALID_STATUSES

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
