from flask import Blueprint, jsonify, request

from app.middleware import require_auth, require_role
from app.models.base import db
from app.models.whatsapp_template import WhatsAppTemplate, DEFAULT_TEMPLATES
from app.models.whatsapp_activity import WhatsAppActivity
from app.models.lead import Lead
from app.utils.activity import log_activity

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/api/whatsapp')

ASSET_TYPES = [
    'brochure',
    'price_list',
    'floor_plan',
    'payment_plan',
    'location_map',
    'gallery_pdf',
    'custom_pdf',
]


def _seed_default_templates(tenant_id: int, created_by: int):
    """Seed the 10 default templates for a tenant if none exist yet."""
    existing = WhatsAppTemplate.query.filter_by(tenant_id=tenant_id).count()
    if existing > 0:
        return
    for t in DEFAULT_TEMPLATES:
        tmpl = WhatsAppTemplate(
            tenant_id=tenant_id,
            name=t['name'],
            category=t['category'],
            body_text=t['body_text'],
            variables=t['variables'],
            is_active=True,
            created_by=created_by,
            sort_order=t['sort_order'],
        )
        db.session.add(tmpl)
    db.session.commit()


# ── Templates ─────────────────────────────────────────────────────────────

@whatsapp_bp.route('/templates', methods=['GET'])
@require_auth
def list_templates():
    tid = request.current_tenant_id
    user = request.current_user
    # Auto-seed defaults on first access per tenant
    _seed_default_templates(tid, user.id)

    templates = (
        WhatsAppTemplate.query
        .filter_by(tenant_id=tid, is_active=True)
        .order_by(WhatsAppTemplate.sort_order, WhatsAppTemplate.id)
        .all()
    )
    return jsonify({'templates': [t.to_dict() for t in templates]}), 200


@whatsapp_bp.route('/templates/all', methods=['GET'])
@require_role('superadmin')
def list_all_templates():
    """Admin view — includes inactive templates."""
    tid = request.current_tenant_id
    user = request.current_user
    _seed_default_templates(tid, user.id)

    templates = (
        WhatsAppTemplate.query
        .filter_by(tenant_id=tid)
        .order_by(WhatsAppTemplate.sort_order, WhatsAppTemplate.id)
        .all()
    )
    return jsonify({'templates': [t.to_dict() for t in templates]}), 200


@whatsapp_bp.route('/templates', methods=['POST'])
@require_role('superadmin')
def create_template():
    user = request.current_user
    tid = user.tenant_id
    data = request.get_json() or {}

    name = (data.get('name') or '').strip()
    body_text = (data.get('body_text') or '').strip()
    if not name or not body_text:
        return jsonify({'error': 'name and body_text are required'}), 400

    tmpl = WhatsAppTemplate(
        tenant_id=tid,
        name=name,
        category=data.get('category', 'general'),
        body_text=body_text,
        variables=data.get('variables') or [],
        is_active=data.get('is_active', True),
        created_by=user.id,
        sort_order=data.get('sort_order', 99),
    )
    db.session.add(tmpl)
    db.session.commit()

    log_activity(user.id, 'create_wa_template', 'whatsapp', tmpl.id, 'WhatsAppTemplate',
                 description=f'Created WhatsApp template: {name}')
    return jsonify({'template': tmpl.to_dict()}), 201


@whatsapp_bp.route('/templates/<int:template_id>', methods=['PUT'])
@require_role('superadmin')
def update_template(template_id):
    user = request.current_user
    tid = user.tenant_id
    tmpl = WhatsAppTemplate.query.filter_by(id=template_id, tenant_id=tid).first()
    if not tmpl:
        return jsonify({'error': 'Template not found'}), 404

    data = request.get_json() or {}
    if 'name' in data:
        tmpl.name = (data['name'] or '').strip() or tmpl.name
    if 'category' in data:
        tmpl.category = data['category']
    if 'body_text' in data:
        tmpl.body_text = (data['body_text'] or '').strip() or tmpl.body_text
    if 'variables' in data:
        tmpl.variables = data['variables'] or []
    if 'is_active' in data:
        tmpl.is_active = bool(data['is_active'])
    if 'sort_order' in data:
        tmpl.sort_order = int(data['sort_order'])

    db.session.commit()
    log_activity(user.id, 'update_wa_template', 'whatsapp', template_id, 'WhatsAppTemplate',
                 description=f'Updated WhatsApp template: {tmpl.name}')
    return jsonify({'template': tmpl.to_dict()}), 200


@whatsapp_bp.route('/templates/<int:template_id>', methods=['DELETE'])
@require_role('superadmin')
def delete_template(template_id):
    user = request.current_user
    tid = user.tenant_id
    tmpl = WhatsAppTemplate.query.filter_by(id=template_id, tenant_id=tid).first()
    if not tmpl:
        return jsonify({'error': 'Template not found'}), 404

    tmpl.is_active = False
    db.session.commit()
    log_activity(user.id, 'delete_wa_template', 'whatsapp', template_id, 'WhatsAppTemplate',
                 description=f'Deactivated WhatsApp template: {tmpl.name}')
    return jsonify({'message': 'Template deleted'}), 200


# ── Activity Log ───────────────────────────────────────────────────────────

@whatsapp_bp.route('/log', methods=['POST'])
@require_auth
def log_whatsapp():
    user = request.current_user
    tid = user.tenant_id
    data = request.get_json() or {}

    lead_id = data.get('lead_id')
    if not lead_id:
        return jsonify({'error': 'lead_id is required'}), 400

    lead = Lead.query.filter_by(id=lead_id, tenant_id=tid).first()
    if not lead:
        return jsonify({'error': 'Lead not found'}), 404

    phone_used = (data.get('phone_used') or '').strip()
    phone_type = data.get('phone_type', 'primary')
    if phone_type not in ('primary', 'alternate'):
        phone_type = 'primary'

    template_id = data.get('template_id')
    template_name = (data.get('template_name') or '').strip() or None
    documents_shared = data.get('documents_shared') or []
    if not isinstance(documents_shared, list):
        documents_shared = []
    message_preview = (data.get('message_preview') or '').strip()[:1000] or None

    activity = WhatsAppActivity(
        tenant_id=tid,
        lead_id=lead_id,
        user_id=user.id,
        template_id=template_id if template_id else None,
        template_name=template_name,
        phone_used=phone_used or None,
        phone_type=phone_type,
        documents_shared=documents_shared,
        message_preview=message_preview,
    )
    db.session.add(activity)
    db.session.commit()

    log_activity(user.id, 'whatsapp_opened', 'whatsapp', lead_id, 'Lead',
                 description=f'WhatsApp opened for lead #{lead_id}')
    return jsonify({'activity': activity.to_dict()}), 201


@whatsapp_bp.route('/activity', methods=['GET'])
@require_auth
def get_whatsapp_activity():
    user = request.current_user
    tid = user.tenant_id
    lead_id = request.args.get('lead_id', type=int)
    limit = min(request.args.get('limit', 50, type=int), 200)

    q = WhatsAppActivity.query.filter_by(tenant_id=tid)

    # Non-admins see only their own activity
    if user.role not in ('superadmin', 'platform_owner', 'sales_manager'):
        q = q.filter_by(user_id=user.id)

    if lead_id:
        q = q.filter_by(lead_id=lead_id)

    activities = q.order_by(WhatsAppActivity.created_at.desc()).limit(limit).all()
    return jsonify({'activities': [a.to_dict() for a in activities]}), 200
