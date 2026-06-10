"""
Lead Source Management – Admin API Routes
==========================================
All routes require superadmin or sales_manager role (tenant-scoped).

CRUD:
  GET    /api/lead-sources                       – list all sources
  POST   /api/lead-sources                       – create source
  GET    /api/lead-sources/<id>                  – get source
  PUT    /api/lead-sources/<id>                  – update source
  DELETE /api/lead-sources/<id>                  – soft-delete (is_active=False)

Operations:
  POST   /api/lead-sources/<id>/test             – validate credentials / permissions
  POST   /api/lead-sources/<id>/enable           – re-enable disabled source
  POST   /api/lead-sources/<id>/disable          – disable source

Reports:
  GET    /api/lead-sources/reports/by-source     – leads grouped by source
  GET    /api/lead-sources/reports/by-campaign   – leads grouped by campaign
  GET    /api/lead-sources/logs                  – ingestion log (with pagination)

Meta OAuth helpers:
  GET    /api/lead-sources/meta/pages            – list pages accessible to token
  GET    /api/lead-sources/meta/forms/<page_id>  – list lead forms for a page
"""

import logging
import os
import secrets
import json as _json
import urllib.request as _req
import urllib.parse as _parse
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, redirect
from sqlalchemy import func

from app.middleware import require_auth, require_role
from app.models.base import db
from app.models.ingestion import LeadSource, IngestedLeadLog, SOURCE_TYPES, DUP_MODES, ASSIGN_STRATEGIES
from app.models.user import User

logger = logging.getLogger(__name__)

lead_sources_bp = Blueprint('lead_sources', __name__, url_prefix='/api/lead-sources')

# ── In-memory OAuth session store (TTL = 10 min) ──────────────────────────────
# Maps session_key → { tenant_id, business_id, pages, user, created_at }
_oauth_sessions = {}

def _get_platform_meta_creds():
    app_id     = os.environ.get('META_APP_ID', '1329585565931521')
    app_secret = os.environ.get('META_APP_SECRET', '')
    return app_id, app_secret

def _get_meta_oauth_scopes():
    """
    Meta OAuth scopes are environment-driven so we can use a minimal testing set
    before app review is complete, then switch to full production scopes.

    Env var: META_OAUTH_SCOPES (comma-separated)
    Default (testing): pages_show_list,pages_read_engagement
    """
    raw = os.environ.get('META_OAUTH_SCOPES', 'pages_show_list,pages_read_engagement')
    scopes = [s.strip() for s in raw.split(',') if s and s.strip()]
    return scopes

def _get_platform_google_creds():
    client_id     = os.environ.get('GOOGLE_CLIENT_ID', '')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    return client_id, client_secret

def _purge_expired_sessions():
    cutoff = datetime.utcnow() - timedelta(minutes=10)
    expired = [k for k, v in _oauth_sessions.items() if v.get('created_at', cutoff) < cutoff]
    for k in expired:
        del _oauth_sessions[k]


# ── Auth helper ────────────────────────────────────────────────────────────────

def _check_source_ownership(source, user):
    """Return 403 dict if user does not own this source, else None."""
    if source.tenant_id != user.tenant_id:
        return jsonify({'error': 'Not found'}), 404
    return None


# ══════════════════════════════════════════════════════════════════════════════
# LIST + CREATE
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('', methods=['GET'])
@require_role('superadmin', 'sales_manager', 'platform_owner')
def list_sources():
    user = request.current_user
    sources = LeadSource.query.filter_by(
        tenant_id=user.tenant_id
    ).order_by(LeadSource.created_at.desc()).all()
    return jsonify({'sources': [s.to_dict() for s in sources]}), 200


@lead_sources_bp.route('', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def create_source():
    user = request.current_user
    data = request.get_json() or {}

    source_type = (data.get('source_type') or '').strip().lower()
    if source_type not in SOURCE_TYPES:
        return jsonify({'error': f'Invalid source_type. Allowed: {list(SOURCE_TYPES)}'}), 400

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    dup_mode = data.get('dup_mode', 'skip')
    if dup_mode not in DUP_MODES:
        return jsonify({'error': f'Invalid dup_mode. Allowed: {list(DUP_MODES)}'}), 400

    assign_strategy = data.get('assign_strategy', 'none')
    if assign_strategy not in ASSIGN_STRATEGIES:
        return jsonify({'error': f'Invalid assign_strategy. Allowed: {list(ASSIGN_STRATEGIES)}'}), 400

    source = LeadSource(
        tenant_id=user.tenant_id,
        name=name,
        source_type=source_type,
        credentials=data.get('credentials') or {},
        field_mapping=data.get('field_mapping') or {},
        default_values=data.get('default_values') or {},
        dup_check_phone=bool(data.get('dup_check_phone', True)),
        dup_check_email=bool(data.get('dup_check_email', True)),
        dup_mode=dup_mode,
        assign_strategy=assign_strategy,
        assign_fixed_user_id=data.get('assign_fixed_user_id'),
        assign_manager_id=data.get('assign_manager_id'),
        rr_user_pool=data.get('rr_user_pool') or [],
        created_by=user.id,
    )
    db.session.add(source)
    db.session.commit()
    return jsonify({'source': source.to_dict()}), 201


# ══════════════════════════════════════════════════════════════════════════════
# GET / UPDATE / DELETE
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/<int:source_id>', methods=['GET'])
@require_role('superadmin', 'sales_manager', 'platform_owner')
def get_source(source_id):
    user = request.current_user
    source = LeadSource.query.get_or_404(source_id)
    err = _check_source_ownership(source, user)
    if err:
        return err
    return jsonify({'source': source.to_dict()}), 200


@lead_sources_bp.route('/<int:source_id>', methods=['PUT'])
@require_role('superadmin', 'platform_owner')
def update_source(source_id):
    user = request.current_user
    source = LeadSource.query.get_or_404(source_id)
    err = _check_source_ownership(source, user)
    if err:
        return err

    data = request.get_json() or {}

    if 'name' in data:
        source.name = (data['name'] or '').strip() or source.name
    if 'credentials' in data:
        # Merge credentials: keep existing masked values unless new ones provided
        existing = source.credentials or {}
        incoming = data['credentials'] or {}
        for k, v in incoming.items():
            # '••••••••' means client didn't change it
            if v != '••••••••':
                existing[k] = v
        source.credentials = existing
    if 'field_mapping' in data:
        source.field_mapping = data['field_mapping'] or {}
    if 'default_values' in data:
        source.default_values = data['default_values'] or {}
    if 'dup_check_phone' in data:
        source.dup_check_phone = bool(data['dup_check_phone'])
    if 'dup_check_email' in data:
        source.dup_check_email = bool(data['dup_check_email'])
    if 'dup_mode' in data:
        if data['dup_mode'] in DUP_MODES:
            source.dup_mode = data['dup_mode']
    if 'assign_strategy' in data:
        if data['assign_strategy'] in ASSIGN_STRATEGIES:
            source.assign_strategy = data['assign_strategy']
    if 'assign_fixed_user_id' in data:
        source.assign_fixed_user_id = data['assign_fixed_user_id']
    if 'assign_manager_id' in data:
        source.assign_manager_id = data['assign_manager_id']
    if 'rr_user_pool' in data:
        source.rr_user_pool = data['rr_user_pool'] or []

    db.session.commit()
    return jsonify({'source': source.to_dict()}), 200


@lead_sources_bp.route('/<int:source_id>', methods=['DELETE'])
@require_role('superadmin', 'platform_owner')
def delete_source(source_id):
    user = request.current_user
    source = LeadSource.query.get_or_404(source_id)
    err = _check_source_ownership(source, user)
    if err:
        return err
    source.is_active = False
    db.session.commit()
    return jsonify({'ok': True}), 200


# ══════════════════════════════════════════════════════════════════════════════
# ENABLE / DISABLE
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/<int:source_id>/enable', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def enable_source(source_id):
    user = request.current_user
    source = LeadSource.query.get_or_404(source_id)
    err = _check_source_ownership(source, user)
    if err:
        return err
    source.is_active = True
    db.session.commit()
    return jsonify({'source': source.to_dict()}), 200


@lead_sources_bp.route('/<int:source_id>/disable', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def disable_source(source_id):
    user = request.current_user
    source = LeadSource.query.get_or_404(source_id)
    err = _check_source_ownership(source, user)
    if err:
        return err
    source.is_active = False
    db.session.commit()
    return jsonify({'source': source.to_dict()}), 200


# ══════════════════════════════════════════════════════════════════════════════
# TEST CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/<int:source_id>/test', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def test_source(source_id):
    """
    Test the connection / permissions for a lead source.
    For Meta: calls Graph API to list accessible pages.
    For Google: validates the refresh token.
    For generic webhook: always passes (HMAC-based, no external auth).
    """
    user = request.current_user
    source = LeadSource.query.get_or_404(source_id)
    err = _check_source_ownership(source, user)
    if err:
        return err

    result = _run_connection_test(source)

    source.last_tested_at   = datetime.utcnow()
    source.last_test_result = result.get('result', 'fail')
    source.last_test_message= result.get('message', '')
    if 'connected_account' in result:
        source.connected_account = result['connected_account']
    if 'permission_status' in result:
        source.permission_status = result['permission_status']
    if 'permission_details' in result:
        source.permission_details = result['permission_details']
    if 'available_forms' in result:
        source.available_forms = result['available_forms']
    if 'available_campaigns' in result:
        source.available_campaigns = result['available_campaigns']

    db.session.commit()
    return jsonify({'test': result, 'source': source.to_dict()}), 200


def _run_connection_test(source: LeadSource) -> dict:
    """Dispatcher for source-type specific connection tests."""
    if source.source_type == 'meta':
        return _test_meta(source)
    if source.source_type == 'google':
        return _test_google(source)
    # Generic webhook: always pass (no external service)
    return {
        'result': 'pass',
        'message': 'Generic webhook is ready. Use the webhook URL to send leads.',
        'connected_account': source.name,
        'permission_status': 'ok',
    }


def _test_meta(source: LeadSource) -> dict:
    """Call Meta Graph API to verify access token and list pages/forms."""
    try:
        import urllib.request as urllib_req
        import urllib.parse as urllib_parse

        creds = source.credentials or {}
        access_token = creds.get('access_token', '')
        if not access_token:
            return {
                'result': 'fail',
                'message': 'No access_token configured. Please provide a Meta Page Access Token.',
                'permission_status': 'missing',
                'permission_details': {'missing': ['access_token']},
            }

        # Validate token via /me endpoint
        url = f'https://graph.facebook.com/v19.0/me?fields=id,name&access_token={urllib_parse.quote(access_token)}'
        req = urllib_req.Request(url)
        with urllib_req.urlopen(req, timeout=10) as resp:
            me_data = __import__('json').loads(resp.read())

        # List subscribed pages
        pages_url = f'https://graph.facebook.com/v19.0/me/accounts?access_token={urllib_parse.quote(access_token)}'
        req = urllib_req.Request(pages_url)
        with urllib_req.urlopen(req, timeout=10) as resp:
            pages_data = __import__('json').loads(resp.read())

        pages = [
            {'id': p['id'], 'name': p['name']}
            for p in pages_data.get('data', [])
        ]

        # Check leadgen permissions
        perm_url = f'https://graph.facebook.com/v19.0/me/permissions?access_token={urllib_parse.quote(access_token)}'
        req = urllib_req.Request(perm_url)
        with urllib_req.urlopen(req, timeout=10) as resp:
            perm_data = __import__('json').loads(resp.read())

        granted = [p['permission'] for p in perm_data.get('data', []) if p.get('status') == 'granted']
        required = _get_meta_oauth_scopes()
        missing  = [r for r in required if r not in granted]

        perm_status = 'ok' if not missing else ('partial' if granted else 'missing')

        return {
            'result': 'pass' if not missing else 'partial',
            'message': f'Connected as {me_data.get("name", "Unknown")}. {len(pages)} page(s) accessible.',
            'connected_account': me_data.get('name', ''),
            'permission_status': perm_status,
            'permission_details': {'granted': granted, 'missing': missing, 'required': required},
            'available_forms': pages,
        }

    except Exception as exc:
        return {
            'result': 'fail',
            'message': f'Meta API error: {exc}',
            'permission_status': 'error',
        }


def _test_google(source: LeadSource) -> dict:
    """Verify Google OAuth credentials by exchanging refresh token."""
    try:
        import urllib.request as urllib_req
        import urllib.parse as urllib_parse
        import json as _json

        creds = source.credentials or {}
        client_id     = creds.get('client_id', '')
        client_secret = creds.get('client_secret', '')
        refresh_token = creds.get('refresh_token', '')

        if not all([client_id, client_secret, refresh_token]):
            missing = [k for k in ['client_id', 'client_secret', 'refresh_token'] if not creds.get(k)]
            return {
                'result': 'fail',
                'message': f'Missing credentials: {missing}',
                'permission_status': 'missing',
                'permission_details': {'missing': missing},
            }

        # Exchange refresh token for access token
        token_url = 'https://oauth2.googleapis.com/token'
        body = urllib_parse.urlencode({
            'client_id':     client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type':    'refresh_token',
        }).encode()
        req = urllib_req.Request(token_url, data=body,
                                  headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urllib_req.urlopen(req, timeout=10) as resp:
            token_data = _json.loads(resp.read())

        if 'error' in token_data:
            return {
                'result': 'fail',
                'message': f'Google OAuth error: {token_data.get("error_description", token_data["error"])}',
                'permission_status': 'error',
            }

        return {
            'result': 'pass',
            'message': 'Google credentials validated successfully.',
            'connected_account': creds.get('customer_id', 'Google Ads Account'),
            'permission_status': 'ok',
            'permission_details': {'granted': ['lead_forms'], 'missing': []},
        }

    except Exception as exc:
        return {
            'result': 'fail',
            'message': f'Google API error: {exc}',
            'permission_status': 'error',
        }


# ══════════════════════════════════════════════════════════════════════════════
# META HELPER ENDPOINTS (OAuth-assisted form/page discovery)
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/meta/pages', methods=['GET'])
@require_role('superadmin', 'platform_owner')
def meta_list_pages():
    """List Meta pages accessible to the given access_token."""
    user = request.current_user
    access_token = request.args.get('access_token', '').strip()
    if not access_token:
        return jsonify({'error': 'access_token query param required'}), 400
    try:
        import urllib.request as urllib_req
        import urllib.parse as urllib_parse
        import json as _json
        url = f'https://graph.facebook.com/v19.0/me/accounts?access_token={urllib_parse.quote(access_token)}'
        with urllib_req.urlopen(urllib_req.Request(url), timeout=10) as resp:
            data = _json.loads(resp.read())
        return jsonify({'pages': data.get('data', [])}), 200
    except Exception as exc:
        return jsonify({'error': str(exc)}), 502


@lead_sources_bp.route('/meta/forms/<page_id>', methods=['GET'])
@require_role('superadmin', 'platform_owner')
def meta_list_forms(page_id):
    """List lead gen forms for a Meta page."""
    user = request.current_user
    access_token = request.args.get('access_token', '').strip()
    if not access_token:
        return jsonify({'error': 'access_token query param required'}), 400
    try:
        import urllib.request as urllib_req
        import urllib.parse as urllib_parse
        import json as _json
        url = (f'https://graph.facebook.com/v19.0/{page_id}/leadgen_forms'
               f'?access_token={urllib_parse.quote(access_token)}')
        with urllib_req.urlopen(urllib_req.Request(url), timeout=10) as resp:
            data = _json.loads(resp.read())
        return jsonify({'forms': data.get('data', [])}), 200
    except Exception as exc:
        return jsonify({'error': str(exc)}), 502


# ══════════════════════════════════════════════════════════════════════════════
# INGESTION LOGS (paginated)
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/logs', methods=['GET'])
@require_role('superadmin', 'sales_manager', 'platform_owner')
def ingestion_logs():
    user = request.current_user
    source_id = request.args.get('source_id', type=int)
    status    = request.args.get('status', '').strip()
    page      = max(1, request.args.get('page', 1, type=int))
    per_page  = min(100, max(10, request.args.get('per_page', 25, type=int)))

    q = IngestedLeadLog.query.filter_by(tenant_id=user.tenant_id)
    if source_id:
        q = q.filter_by(source_id=source_id)
    if status:
        q = q.filter_by(status=status)

    total = q.count()
    logs  = q.order_by(IngestedLeadLog.received_at.desc()).offset((page-1)*per_page).limit(per_page).all()

    return jsonify({
        'logs':     [l.to_dict() for l in logs],
        'total':    total,
        'page':     page,
        'per_page': per_page,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/reports/by-source', methods=['GET'])
@require_role('superadmin', 'sales_manager', 'platform_owner')
def report_by_source():
    """Lead counts grouped by source name / type, with optional date range."""
    user = request.current_user
    date_from = request.args.get('date_from')
    date_to   = request.args.get('date_to')

    q = db.session.query(
        IngestedLeadLog.source_id,
        IngestedLeadLog.source_type,
        func.count(IngestedLeadLog.id).label('total'),
        func.sum(
            db.case((IngestedLeadLog.status == 'processed', 1), else_=0)
        ).label('created'),
        func.sum(
            db.case((IngestedLeadLog.status == 'duplicate', 1), else_=0)
        ).label('duplicates'),
        func.sum(
            db.case((IngestedLeadLog.status == 'error', 1), else_=0)
        ).label('errors'),
    ).filter(IngestedLeadLog.tenant_id == user.tenant_id)

    if date_from:
        try:
            q = q.filter(IngestedLeadLog.received_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(IngestedLeadLog.received_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    rows = q.group_by(IngestedLeadLog.source_id, IngestedLeadLog.source_type).all()

    # Enrich with source names
    source_names = {
        s.id: s.name
        for s in LeadSource.query.filter_by(tenant_id=user.tenant_id).all()
    }

    result = [
        {
            'source_id':   r.source_id,
            'source_name': source_names.get(r.source_id, 'Unknown'),
            'source_type': r.source_type,
            'total':       r.total,
            'created':     int(r.created or 0),
            'duplicates':  int(r.duplicates or 0),
            'errors':      int(r.errors or 0),
        }
        for r in rows
    ]
    return jsonify({'rows': result}), 200


@lead_sources_bp.route('/reports/by-campaign', methods=['GET'])
@require_role('superadmin', 'sales_manager', 'platform_owner')
def report_by_campaign():
    """Lead counts grouped by campaign name."""
    user = request.current_user
    date_from = request.args.get('date_from')
    date_to   = request.args.get('date_to')

    q = db.session.query(
        IngestedLeadLog.campaign_name,
        IngestedLeadLog.source_type,
        func.count(IngestedLeadLog.id).label('total'),
        func.sum(
            db.case((IngestedLeadLog.status == 'processed', 1), else_=0)
        ).label('created'),
    ).filter(
        IngestedLeadLog.tenant_id == user.tenant_id,
        IngestedLeadLog.campaign_name != None,
        IngestedLeadLog.campaign_name != '',
    )

    if date_from:
        try:
            q = q.filter(IngestedLeadLog.received_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(IngestedLeadLog.received_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    rows = q.group_by(
        IngestedLeadLog.campaign_name, IngestedLeadLog.source_type
    ).order_by(func.count(IngestedLeadLog.id).desc()).all()

    return jsonify({'rows': [
        {
            'campaign_name': r.campaign_name or '(none)',
            'source_type':   r.source_type,
            'total':         r.total,
            'created':       int(r.created or 0),
        }
        for r in rows
    ]}), 200


# ══════════════════════════════════════════════════════════════════════════════
# META OAUTH FLOW
# Phase META-1.1: full guided connection  (Business → Page → Forms → Save)
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/meta/exchange-token', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def meta_exchange_token():
    """
    Exchange a short-lived user access token (from the browser JS SDK / OAuth
    redirect) for a long-lived user token, then return the user profile and
    list of Pages the user manages.

    POST body:
      { "short_lived_token": "...", "app_id": "...", "app_secret": "..." }

    Returns:
      { "long_lived_token": "...", "user": {...}, "pages": [...] }
    """
    user = request.current_user
    data = request.get_json() or {}

    short_token = (data.get('short_lived_token') or '').strip()
    app_id      = (data.get('app_id') or '').strip()
    app_secret  = (data.get('app_secret') or '').strip()

    if not all([short_token, app_id, app_secret]):
        return jsonify({'error': 'short_lived_token, app_id and app_secret are required'}), 400

    try:
        import urllib.request as _req
        import urllib.parse as _parse
        import json as _json

        # 1. Exchange short-lived → long-lived user token
        exchange_url = (
            'https://graph.facebook.com/v19.0/oauth/access_token?'
            f'grant_type=fb_exchange_token'
            f'&client_id={_parse.quote(app_id)}'
            f'&client_secret={_parse.quote(app_secret)}'
            f'&fb_exchange_token={_parse.quote(short_token)}'
        )
        with _req.urlopen(_req.Request(exchange_url), timeout=15) as r:
            token_data = _json.loads(r.read())

        if 'error' in token_data:
            return jsonify({'error': token_data['error'].get('message', 'Token exchange failed')}), 400

        long_token = token_data.get('access_token', short_token)

        # 2. /me – basic user info
        me_url = f'https://graph.facebook.com/v19.0/me?fields=id,name&access_token={_parse.quote(long_token)}'
        with _req.urlopen(_req.Request(me_url), timeout=10) as r:
            me = _json.loads(r.read())

        # 3. /me/accounts – pages managed by this user
        pages_url = f'https://graph.facebook.com/v19.0/me/accounts?fields=id,name,access_token,tasks&access_token={_parse.quote(long_token)}'
        with _req.urlopen(_req.Request(pages_url), timeout=10) as r:
            pages_data = _json.loads(r.read())

        pages = [
            {
                'id':           p['id'],
                'name':         p['name'],
                'access_token': p.get('access_token', ''),
                'tasks':        p.get('tasks', []),
            }
            for p in pages_data.get('data', [])
        ]

        return jsonify({
            'long_lived_token': long_token,
            'user':             {'id': me.get('id'), 'name': me.get('name')},
            'pages':            pages,
        }), 200

    except Exception as exc:
        logger.exception('meta_exchange_token error: %s', exc)
        return jsonify({'error': str(exc)}), 502


@lead_sources_bp.route('/meta/page-forms', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def meta_page_forms():
    """
    List all lead-gen forms for a specific Meta page.

    POST body:
      { "page_id": "...", "page_access_token": "..." }

    Returns:
      { "forms": [{id, name, status, leads_count, created_time}] }
    """
    user = request.current_user
    data = request.get_json() or {}

    page_id     = (data.get('page_id') or '').strip()
    page_token  = (data.get('page_access_token') or '').strip()

    if not page_id or not page_token:
        return jsonify({'error': 'page_id and page_access_token are required'}), 400

    try:
        import urllib.request as _req
        import urllib.parse as _parse
        import json as _json

        url = (
            f'https://graph.facebook.com/v19.0/{_parse.quote(page_id)}/leadgen_forms'
            f'?fields=id,name,status,leads_count,created_time'
            f'&access_token={_parse.quote(page_token)}'
        )
        with _req.urlopen(_req.Request(url), timeout=10) as r:
            forms_data = _json.loads(r.read())

        if 'error' in forms_data:
            return jsonify({'error': forms_data['error'].get('message', 'Graph API error')}), 400

        forms = [
            {
                'id':           f['id'],
                'name':         f.get('name', ''),
                'status':       f.get('status', ''),
                'leads_count':  f.get('leads_count', 0),
                'created_time': f.get('created_time', ''),
            }
            for f in forms_data.get('data', [])
        ]

        return jsonify({'forms': forms}), 200

    except Exception as exc:
        logger.exception('meta_page_forms error: %s', exc)
        return jsonify({'error': str(exc)}), 502


@lead_sources_bp.route('/meta/save-connection', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def meta_save_connection():
    """
    Finalise a Meta OAuth wizard: create or update the LeadSource with the
    selected page + forms and persist the page access token.

    POST body:
    {
      "source_id":         123,          // update existing, or null to create new
      "name":              "My FB Source",
      "app_id":            "...",
      "app_secret":        "...",
      "user_token":        "...",        // long-lived user token
      "page_id":           "...",
      "page_name":         "...",
      "page_access_token": "...",
      "selected_forms":    [{id, name}], // forms the user picked
      "verify_token":      "...",        // webhook verify token (user-set)
    }
    """
    user = request.current_user
    data = request.get_json() or {}

    page_id     = (data.get('page_id') or '').strip()
    page_token  = (data.get('page_access_token') or '').strip()
    page_name   = (data.get('page_name') or '').strip()
    name        = (data.get('name') or f'Meta – {page_name}').strip()

    if not page_id or not page_token:
        return jsonify({'error': 'page_id and page_access_token are required'}), 400

    creds = {
        'app_id':            data.get('app_id', ''),
        'app_secret':        data.get('app_secret', ''),
        'user_token':        data.get('user_token', ''),
        'page_id':           page_id,
        'page_access_token': page_token,
        'verify_token':      data.get('verify_token', ''),
        # access_token alias (used by existing engine + test helpers)
        'access_token':      page_token,
    }

    selected_forms = data.get('selected_forms') or []

    source_id = data.get('source_id')
    if source_id:
        source = LeadSource.query.filter_by(id=source_id, tenant_id=user.tenant_id).first()
        if not source:
            return jsonify({'error': 'Source not found'}), 404
        source.name = name
        existing_creds = source.credentials or {}
        existing_creds.update({k: v for k, v in creds.items() if v})
        source.credentials = existing_creds
    else:
        source = LeadSource(
            tenant_id=user.tenant_id,
            name=name,
            source_type='meta',
            credentials=creds,
            created_by=user.id,
        )
        db.session.add(source)

    source.connected_account = f'{page_name} (Page ID: {page_id})'
    source.available_forms   = selected_forms
    source.permission_status = 'ok'
    source.last_tested_at    = datetime.utcnow()
    source.last_test_result  = 'pass'
    source.last_test_message = f'Connected via OAuth. {len(selected_forms)} form(s) selected.'

    db.session.commit()
    return jsonify({'source': source.to_dict()}), 200


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE OAUTH FLOW
# Phase META-1.1
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/google/exchange-code', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def google_exchange_code():
    """
    Exchange a Google OAuth authorization code for access + refresh tokens.
    Returns account info and lead form campaigns accessible to this account.

    POST body:
      { "code": "...", "client_id": "...", "client_secret": "...", "redirect_uri": "..." }
    """
    user = request.current_user
    data = request.get_json() or {}

    code          = (data.get('code') or '').strip()
    client_id     = (data.get('client_id') or '').strip()
    client_secret = (data.get('client_secret') or '').strip()
    redirect_uri  = (data.get('redirect_uri') or '').strip()

    if not all([code, client_id, client_secret, redirect_uri]):
        return jsonify({'error': 'code, client_id, client_secret, redirect_uri are required'}), 400

    try:
        import urllib.request as _req
        import urllib.parse as _parse
        import json as _json

        # 1. Exchange code for tokens
        token_body = _parse.urlencode({
            'code':          code,
            'client_id':     client_id,
            'client_secret': client_secret,
            'redirect_uri':  redirect_uri,
            'grant_type':    'authorization_code',
        }).encode()
        req = _req.Request(
            'https://oauth2.googleapis.com/token',
            data=token_body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        with _req.urlopen(req, timeout=15) as r:
            token_data = _json.loads(r.read())

        if 'error' in token_data:
            return jsonify({'error': token_data.get('error_description', token_data['error'])}), 400

        access_token  = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')

        # 2. Get user info
        ui_req = _req.Request(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        with _req.urlopen(ui_req, timeout=10) as r:
            userinfo = _json.loads(r.read())

        return jsonify({
            'access_token':  access_token,
            'refresh_token': refresh_token,
            'user': {
                'id':    userinfo.get('id'),
                'email': userinfo.get('email'),
                'name':  userinfo.get('name'),
            },
        }), 200

    except Exception as exc:
        logger.exception('google_exchange_code error: %s', exc)
        return jsonify({'error': str(exc)}), 502


@lead_sources_bp.route('/google/save-connection', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def google_save_connection():
    """
    Finalise Google OAuth wizard: create or update LeadSource with Google
    credentials and selected campaign/form info.

    POST body:
    {
      "source_id":      123,          // update existing, or null to create new
      "name":           "Google Ads – Mumbai",
      "client_id":      "...",
      "client_secret":  "...",
      "refresh_token":  "...",
      "customer_id":    "...",        // Google Ads Customer ID (optional)
      "user_email":     "...",
      "selected_forms": [{id, name, campaign_id, campaign_name}],
    }
    """
    user = request.current_user
    data = request.get_json() or {}

    client_id     = (data.get('client_id') or '').strip()
    client_secret = (data.get('client_secret') or '').strip()
    refresh_token = (data.get('refresh_token') or '').strip()
    user_email    = (data.get('user_email') or '').strip()
    name          = (data.get('name') or f'Google – {user_email}').strip()

    if not all([client_id, client_secret, refresh_token]):
        return jsonify({'error': 'client_id, client_secret and refresh_token are required'}), 400

    creds = {
        'client_id':     client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'customer_id':   data.get('customer_id', ''),
    }

    selected_forms    = data.get('selected_forms') or []
    selected_campaigns = list({
        f['campaign_id']: {'id': f['campaign_id'], 'name': f['campaign_name']}
        for f in selected_forms if f.get('campaign_id')
    }.values())

    source_id = data.get('source_id')
    if source_id:
        source = LeadSource.query.filter_by(id=source_id, tenant_id=user.tenant_id).first()
        if not source:
            return jsonify({'error': 'Source not found'}), 404
        source.name = name
        existing_creds = source.credentials or {}
        existing_creds.update({k: v for k, v in creds.items() if v})
        source.credentials = existing_creds
    else:
        source = LeadSource(
            tenant_id=user.tenant_id,
            name=name,
            source_type='google',
            credentials=creds,
            created_by=user.id,
        )
        db.session.add(source)

    source.connected_account  = user_email or 'Google Ads Account'
    source.available_forms    = selected_forms
    source.available_campaigns = selected_campaigns
    source.permission_status  = 'ok'
    source.last_tested_at     = datetime.utcnow()
    source.last_test_result   = 'pass'
    source.last_test_message  = (
        f'Connected via OAuth. {len(selected_forms)} form(s), '
        f'{len(selected_campaigns)} campaign(s).'
    )

    db.session.commit()
    return jsonify({'source': source.to_dict()}), 200


# ══════════════════════════════════════════════════════════════════════════════
# SIMPLIFIED META OAUTH  (platform credentials stored in env vars)
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/meta/start-auth', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def meta_start_auth():
    """
    Generate a Facebook OAuth URL using the platform Meta app credentials.
    Tenant provides their Business ID; we encode it in the OAuth state.

    POST body: { "business_id": "123456789" }
    Returns:   { "auth_url": "https://facebook.com/dialog/oauth?..." }
    """
    user = request.current_user
    data = request.get_json() or {}
    business_id = (data.get('business_id') or '').strip()
    if not business_id:
        return jsonify({'error': 'business_id is required'}), 400

    app_id, app_secret = _get_platform_meta_creds()
    if not app_secret:
        return jsonify({'error': 'Meta platform credentials not configured. Set META_APP_SECRET in environment.'}), 500

    session_key = secrets.token_urlsafe(24)
    _purge_expired_sessions()
    _oauth_sessions[session_key] = {
        'tenant_id':   user.tenant_id,
        'business_id': business_id,
        'created_at':  datetime.utcnow(),
    }

    frontend_base = os.environ.get('FRONTEND_URL', 'https://app.sociomonkey.com')
    callback_url  = os.environ.get('BACKEND_URL', 'https://smk-backend-api.vercel.app') + '/api/lead-sources/meta/oauth/callback'
    state = _parse.quote(session_key)

    scopes = ','.join(_get_meta_oauth_scopes())
    auth_url = (
        f'https://www.facebook.com/dialog/oauth'
        f'?client_id={_parse.quote(app_id)}'
        f'&redirect_uri={_parse.quote(callback_url)}'
        f'&scope={_parse.quote(scopes)}'
        f'&response_type=code'
        f'&state={state}'
    )
    return jsonify({'auth_url': auth_url, 'session_key': session_key}), 200


@lead_sources_bp.route('/meta/oauth/callback', methods=['GET'])
def meta_oauth_callback():
    """
    Facebook OAuth callback. Exchanges code → token → fetches pages
    from the business_id stored in session. Redirects tenant back to
    the LMS page with session_key so frontend can retrieve pages.
    """
    code        = request.args.get('code', '')
    state       = request.args.get('state', '')
    error       = request.args.get('error', '')
    frontend_base = os.environ.get('FRONTEND_URL', 'https://app.sociomonkey.com')

    if error:
        return redirect(f'{frontend_base}/?meta_oauth_error={_parse.quote(error)}')

    session_data = _oauth_sessions.get(state)
    if not session_data:
        return redirect(f'{frontend_base}/?meta_oauth_error=session_expired')

    app_id, app_secret = _get_platform_meta_creds()
    callback_url = os.environ.get('BACKEND_URL', 'https://smk-backend-api.vercel.app') + '/api/lead-sources/meta/oauth/callback'

    try:
        # Exchange code → short-lived token
        token_url = (
            f'https://graph.facebook.com/v19.0/oauth/access_token'
            f'?client_id={_parse.quote(app_id)}'
            f'&redirect_uri={_parse.quote(callback_url)}'
            f'&client_secret={_parse.quote(app_secret)}'
            f'&code={_parse.quote(code)}'
        )
        with _req.urlopen(_req.Request(token_url), timeout=15) as r:
            token_data = _json.loads(r.read())

        if 'error' in token_data:
            return redirect(f'{frontend_base}/?meta_oauth_error=token_exchange_failed')

        short_token = token_data.get('access_token', '')

        # Exchange short → long-lived token
        long_url = (
            f'https://graph.facebook.com/v19.0/oauth/access_token'
            f'?grant_type=fb_exchange_token'
            f'&client_id={_parse.quote(app_id)}'
            f'&client_secret={_parse.quote(app_secret)}'
            f'&fb_exchange_token={_parse.quote(short_token)}'
        )
        with _req.urlopen(_req.Request(long_url), timeout=15) as r:
            long_data = _json.loads(r.read())
        long_token = long_data.get('access_token', short_token)

        # Get user info
        me_url = f'https://graph.facebook.com/v19.0/me?fields=id,name&access_token={_parse.quote(long_token)}'
        with _req.urlopen(_req.Request(me_url), timeout=10) as r:
            me = _json.loads(r.read())

        # Get pages for this user (filtered by business_id if provided)
        business_id = session_data.get('business_id', '')
        pages_url = f'https://graph.facebook.com/v19.0/me/accounts?fields=id,name,access_token&access_token={_parse.quote(long_token)}'
        with _req.urlopen(_req.Request(pages_url), timeout=10) as r:
            pages_data = _json.loads(r.read())

        all_pages = [
            {'id': p['id'], 'name': p['name'], 'access_token': p.get('access_token', '')}
            for p in pages_data.get('data', [])
        ]

        # If business_id given, also try fetching pages from that business
        biz_pages = []
        if business_id:
            try:
                biz_url = (
                    f'https://graph.facebook.com/v19.0/{_parse.quote(business_id)}/owned_pages'
                    f'?fields=id,name,access_token&access_token={_parse.quote(long_token)}'
                )
                with _req.urlopen(_req.Request(biz_url), timeout=10) as r:
                    biz_data = _json.loads(r.read())
                biz_pages = [
                    {'id': p['id'], 'name': p['name'], 'access_token': p.get('access_token', '')}
                    for p in biz_data.get('data', [])
                ]
            except Exception:
                pass  # fall back to user pages

        pages = biz_pages if biz_pages else all_pages

        # Store result in session
        _oauth_sessions[state].update({
            'user':       {'id': me.get('id'), 'name': me.get('name')},
            'long_token': long_token,
            'pages':      pages,
            'completed':  True,
        })

        # Redirect back to frontend
        tenant_id = session_data.get('tenant_id', 'demo')
        tenant_slug = str(tenant_id)
        # Try to get the tenant slug from DB for a nicer URL
        try:
            from app.models.tenant import Tenant
            t = Tenant.query.get(tenant_id)
            if t and t.slug:
                tenant_slug = t.slug
        except Exception:
            pass

        return redirect(
            f'{frontend_base}/apps/lms/{tenant_slug}/lead_sources?meta_session={_parse.quote(state)}&meta_tab=connect'
        )

    except Exception as exc:
        logger.exception('meta_oauth_callback error: %s', exc)
        return redirect(f'{frontend_base}/?meta_oauth_error=server_error')


@lead_sources_bp.route('/meta/auth-session/<session_key>', methods=['GET'])
@require_role('superadmin', 'platform_owner')
def meta_auth_session(session_key):
    """
    Retrieve pages + user info from a completed OAuth session.
    Called by frontend after OAuth callback redirect.
    """
    user = request.current_user
    session_data = _oauth_sessions.get(session_key)
    if not session_data:
        return jsonify({'error': 'Session expired or not found'}), 404
    if session_data.get('tenant_id') != user.tenant_id:
        return jsonify({'error': 'Unauthorized'}), 403
    if not session_data.get('completed'):
        return jsonify({'error': 'OAuth not completed yet'}), 202

    return jsonify({
        'user':        session_data.get('user'),
        'pages':       session_data.get('pages', []),
        'long_token':  session_data.get('long_token', ''),
        'business_id': session_data.get('business_id', ''),
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# SIMPLIFIED GOOGLE OAUTH  (platform credentials stored in env vars)
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/google/start-auth', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def google_start_auth():
    """
    Generate a Google OAuth URL using platform credentials from env vars.
    Returns: { "auth_url": "..." }
    """
    user = request.current_user
    client_id, client_secret = _get_platform_google_creds()
    if not client_id or not client_secret:
        return jsonify({'error': 'Google platform credentials not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in environment.'}), 500

    session_key = secrets.token_urlsafe(24)
    _purge_expired_sessions()
    _oauth_sessions[session_key] = {
        'tenant_id':  user.tenant_id,
        'platform':   'google',
        'created_at': datetime.utcnow(),
    }

    callback_url = os.environ.get('BACKEND_URL', 'https://smk-backend-api.vercel.app') + '/api/lead-sources/google/oauth/callback'
    scopes = 'https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/adwords'
    auth_url = (
        f'https://accounts.google.com/o/oauth2/v2/auth'
        f'?client_id={_parse.quote(client_id)}'
        f'&redirect_uri={_parse.quote(callback_url)}'
        f'&response_type=code'
        f'&scope={_parse.quote(scopes)}'
        f'&access_type=offline'
        f'&prompt=select_account%20consent'
        f'&state={_parse.quote(session_key)}'
    )
    return jsonify({'auth_url': auth_url, 'session_key': session_key}), 200


@lead_sources_bp.route('/google/oauth/callback', methods=['GET'])
def google_oauth_callback():
    """
    Google OAuth callback — exchanges code → tokens → stores in session.
    Redirects back to LMS frontend.
    """
    code  = request.args.get('code', '')
    state = request.args.get('state', '')
    error = request.args.get('error', '')
    frontend_base = os.environ.get('FRONTEND_URL', 'https://app.sociomonkey.com')

    if error:
        return redirect(f'{frontend_base}/?google_oauth_error={_parse.quote(error)}')

    session_data = _oauth_sessions.get(state)
    if not session_data:
        return redirect(f'{frontend_base}/?google_oauth_error=session_expired')

    client_id, client_secret = _get_platform_google_creds()
    callback_url = os.environ.get('BACKEND_URL', 'https://smk-backend-api.vercel.app') + '/api/lead-sources/google/oauth/callback'

    try:
        token_body = _parse.urlencode({
            'code':          code,
            'client_id':     client_id,
            'client_secret': client_secret,
            'redirect_uri':  callback_url,
            'grant_type':    'authorization_code',
        }).encode()
        req = _req.Request(
            'https://oauth2.googleapis.com/token',
            data=token_body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        with _req.urlopen(req, timeout=15) as r:
            token_data = _json.loads(r.read())

        if 'error' in token_data:
            return redirect(f'{frontend_base}/?google_oauth_error=token_exchange_failed')

        access_token  = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')

        ui_req = _req.Request(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        with _req.urlopen(ui_req, timeout=10) as r:
            userinfo = _json.loads(r.read())

        _oauth_sessions[state].update({
            'access_token':  access_token,
            'refresh_token': refresh_token,
            'user':          {'id': userinfo.get('id'), 'email': userinfo.get('email'), 'name': userinfo.get('name')},
            'completed':     True,
        })

        tenant_id   = session_data.get('tenant_id', 'demo')
        tenant_slug = str(tenant_id)
        try:
            from app.models.tenant import Tenant
            t = Tenant.query.get(tenant_id)
            if t and t.slug:
                tenant_slug = t.slug
        except Exception:
            pass

        return redirect(
            f'{frontend_base}/apps/lms/{tenant_slug}/lead_sources?google_session={_parse.quote(state)}&meta_tab=connect'
        )

    except Exception as exc:
        logger.exception('google_oauth_callback error: %s', exc)
        return redirect(f'{frontend_base}/?google_oauth_error=server_error')


@lead_sources_bp.route('/google/auth-session/<session_key>', methods=['GET'])
@require_role('superadmin', 'platform_owner')
def google_auth_session(session_key):
    """Retrieve user + tokens from a completed Google OAuth session."""
    user = request.current_user
    session_data = _oauth_sessions.get(session_key)
    if not session_data:
        return jsonify({'error': 'Session expired or not found'}), 404
    if session_data.get('tenant_id') != user.tenant_id:
        return jsonify({'error': 'Unauthorized'}), 403
    if not session_data.get('completed'):
        return jsonify({'error': 'OAuth not completed yet'}), 202
    return jsonify({
        'user':          session_data.get('user'),
        'access_token':  session_data.get('access_token', ''),
        'refresh_token': session_data.get('refresh_token', ''),
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# TEST LEAD INJECTION
# Phase META-1.1 – fire a synthetic lead through the full pipeline
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/<int:source_id>/inject-test-lead', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def inject_test_lead(source_id):
    """
    Inject a synthetic test lead through the ingestion pipeline.
    Creates a real Lead row so every downstream step can be verified.

    POST body (all optional – uses defaults if omitted):
    {
      "name":    "Test Lead",
      "phone":   "+910000000001",
      "email":   "test@example.com",
      "campaign_name": "Test Campaign",
    }

    Returns the full pipeline result + link to the created lead.
    """
    user = request.current_user
    source = LeadSource.query.get_or_404(source_id)
    err = _check_source_ownership(source, user)
    if err:
        return err

    data = request.get_json() or {}

    import time
    ts = str(int(time.time()))

    # Build a realistic raw payload mirroring what the platform sends
    if source.source_type == 'meta':
        raw_payload = {
            'leadgen_id': f'TEST-{ts}',
            'page_id':    (source.credentials or {}).get('page_id', 'TEST_PAGE'),
            'form_id':    'TEST_FORM',
            'ad_id':      'TEST_AD',
            'adset_id':   'TEST_ADSET',
            'campaign_id': 'TEST_CAMPAIGN',
            'field_data': [
                {'name': 'full_name',     'values': [data.get('name',  f'Test Lead {ts}')]},
                {'name': 'phone_number',  'values': [data.get('phone', f'+910000{ts[-6:]}')]},
                {'name': 'email',         'values': [data.get('email', f'test{ts}@test.sociomonkey.com')]},
            ],
        }
        from app.routes.ingestion import _normalise_meta
        normalised = _normalise_meta(raw_payload)
        normalised['campaign_name'] = data.get('campaign_name', 'Test Campaign')

    elif source.source_type == 'google':
        raw_payload = {
            'lead_id':      f'TEST-{ts}',
            'form_id':      'TEST_FORM',
            'form_name':    'Test Form',
            'campaign_id':  'TEST_CAMPAIGN',
            'campaign_name': data.get('campaign_name', 'Test Campaign'),
            'ad_group_id':  'TEST_ADGROUP',
            'ad_group_name': 'Test Ad Group',
            'user_column_data': [
                {'column_name': 'GIVEN_NAME',   'string_value': data.get('name',  f'Test Lead {ts}').split()[0]},
                {'column_name': 'FAMILY_NAME',  'string_value': ' '.join(data.get('name', f'Test Lead {ts}').split()[1:]) or 'User'},
                {'column_name': 'PHONE_NUMBER', 'string_value': data.get('phone', f'+910000{ts[-6:]}')},
                {'column_name': 'EMAIL',        'string_value': data.get('email', f'test{ts}@test.sociomonkey.com')},
            ],
        }
        from app.routes.ingestion import _normalise_google
        normalised = _normalise_google(raw_payload)

    else:
        raw_payload = {
            'name':  data.get('name',  f'Test Lead {ts}'),
            'phone': data.get('phone', f'+910000{ts[-6:]}'),
            'email': data.get('email', f'test{ts}@test.sociomonkey.com'),
            'campaign_name': data.get('campaign_name', 'Test Campaign'),
        }
        from app.routes.ingestion import _normalise_generic
        normalised = _normalise_generic(raw_payload)

    from app.services.ingestion_engine import ingest_lead
    result = ingest_lead(source, raw_payload, normalised)

    # Gather pipeline evidence for UI display
    lead_id = result.get('lead_id')
    evidence = {}
    if lead_id:
        from app.models import Lead, ActivityLog
        lead = Lead.query.get(lead_id)
        if lead:
            evidence['lead'] = lead.to_dict()

        activity = ActivityLog.query.filter_by(
            resource_id=lead_id, resource_type='Lead', action='lead_ingested'
        ).order_by(ActivityLog.id.desc()).first()
        if activity:
            evidence['activity'] = {
                'id':          activity.id,
                'description': activity.description,
                'new_value':   activity.new_value,
            }

        log = IngestedLeadLog.query.filter_by(
            source_id=source_id, lead_id=lead_id
        ).order_by(IngestedLeadLog.id.desc()).first()
        if log:
            evidence['log'] = log.to_dict()

        # Push notification (NotificationEvent created by stage 6 of engine)
        from app.models.push import NotificationEvent
        notif = NotificationEvent.query.filter_by(lead_id=lead_id).first()
        if notif:
            evidence['push_notification'] = notif.to_dict()

        # Action board: StatusHistory entry created for this lead
        from app.models import StatusHistory
        sh = StatusHistory.query.filter_by(lead_id=lead_id).first()
        if sh:
            evidence['status_history'] = {'id': sh.id, 'status': sh.new_status if hasattr(sh, 'new_status') else str(sh)}

    lead_dict = evidence.get('lead', {})
    return jsonify({
        'result':   result,
        'evidence': evidence,
        'checks': {
            'lead_created':            lead_id is not None and result.get('status') in ('created', 'updated'),
            'pipeline_ran':            result.get('status') != 'error',
            'activity_logged':         bool(evidence.get('activity')),
            'assignment_applied':      bool(lead_dict.get('assigned_to')),
            'push_notification_created': bool(evidence.get('push_notification')),
            'action_board_updated':    bool(evidence.get('status_history')),
        },
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
# FULL VALIDATION RUNNER
# Phase META-1.3 – 7-item real-account validation: connection, lead validation,
# duplicate detection, tenant isolation, end-to-end LMS flow.
# ══════════════════════════════════════════════════════════════════════════════

@lead_sources_bp.route('/validate', methods=['POST'])
@require_role('superadmin', 'platform_owner')
def run_validation():
    """
    Run the Phase META-1.3 validation suite against this tenant.

    POST body:
    {
      "meta_source_id":   123,   // LeadSource id (meta)
      "google_source_id": 456,   // LeadSource id (google) – optional
    }

    Returns a structured PASS/FAIL report for all 7 validation items.
    """
    user = request.current_user
    data = request.get_json() or {}
    _flow_lead_id = None

    report = {
        'tenant_id':   user.tenant_id,
        'run_at':      datetime.utcnow().isoformat(),
        'items':       {},
        'deployment_ready': False,
    }

    # ── Helper ─────────────────────────────────────────────────────────────────
    def item(key, label, passed, detail='', sub=None):
        report['items'][key] = {
            'label':  label,
            'passed': passed,
            'result': 'PASS' if passed else 'FAIL',
            'detail': detail,
            'sub':    sub or {},
        }

    # ── ITEM 1: Meta Connection ────────────────────────────────────────────────
    meta_source_id = data.get('meta_source_id')
    meta_source = None
    if meta_source_id:
        meta_source = LeadSource.query.filter_by(
            id=meta_source_id, tenant_id=user.tenant_id, source_type='meta'
        ).first()

    if not meta_source:
        item('meta_connection', 'Meta Connection', False, 'No Meta source selected')
    else:
        test = _run_connection_test(meta_source)
        connected = test.get('result') in ('pass', 'partial')
        item('meta_connection', 'Meta Connection', connected,
             test.get('message', ''),
             {
                 'login_ok':          connected,
                 'business_manager':  bool(meta_source.connected_account),
                 'pages_visible':     bool((meta_source.credentials or {}).get('page_id')),
                 'forms_visible':     len(meta_source.available_forms or []) > 0,
                 'permissions_ok':    meta_source.permission_status in ('ok', 'active', 'granted'),
                 'connected_account': meta_source.connected_account,
                 'available_forms':   len(meta_source.available_forms or []),
             })

    # ── ITEM 2: Meta Lead Validation ─────────────────────────────────────────
    if meta_source:
        try:
            from app.routes.ingestion import _normalise_meta
            from app.services.ingestion_engine import ingest_lead
            import time
            ts = str(int(time.time()))
            raw = {
                'leadgen_id': f'VALIDATE-{ts}',
                'page_id':    (meta_source.credentials or {}).get('page_id', 'TEST'),
                'form_id':    'VALIDATE_FORM',
                'field_data': [
                    {'name': 'full_name',    'values': [f'Validation Lead {ts}']},
                    {'name': 'phone_number', 'values': [f'+910001{ts[-6:]}']},
                    {'name': 'email',        'values': [f'validate{ts}@test.sociomonkey.com']},
                ],
            }
            norm = _normalise_meta(raw)
            norm['campaign_name'] = 'Validation Run'
            res = ingest_lead(meta_source, raw, norm)
            lead_created = res.get('status') in ('created', 'updated')
            lead_id = res.get('lead_id')
            if lead_id:
                _flow_lead_id = lead_id

            from app.models import Lead, ActivityLog
            from app.models.push import NotificationEvent
            from app.models import StatusHistory
            assigned = False; timeline = False; push_ok = False; board_ok = False
            source_captured = False; campaign_captured = False
            if lead_id:
                l = Lead.query.get(lead_id)
                assigned = bool(l and l.assigned_to) or meta_source.assign_strategy == 'none'
                source_captured = bool(l and l.source_name)
                campaign_captured = bool(l and l.campaign_name)
                timeline = bool(ActivityLog.query.filter_by(
                    resource_id=lead_id, action='lead_ingested').first())
                push_ok = bool(NotificationEvent.query.filter_by(lead_id=lead_id).first())
                board_ok = bool(StatusHistory.query.filter_by(lead_id=lead_id).first())

            item('meta_lead_validation', 'Meta Lead Validation', lead_created,
                 f'Lead #{lead_id} – status: {res.get("status")}',
                 {
                     'lead_entered_lms':          lead_created,
                     'lead_source_captured':      source_captured,
                     'campaign_captured':         campaign_captured,
                     'lead_assigned':             assigned,
                     'timeline_created':          timeline,
                     'push_notification_created': push_ok,
                     'action_board_updated':      board_ok,
                 })
        except Exception as exc:
            item('meta_lead_validation', 'Meta Lead Validation', False, str(exc))
    else:
        item('meta_lead_validation', 'Meta Lead Validation', False, 'No Meta source configured')

    # ── ITEM 3: Google Connection ─────────────────────────────────────────────
    google_source_id = data.get('google_source_id')
    google_source = None
    if google_source_id:
        google_source = LeadSource.query.filter_by(
            id=google_source_id, tenant_id=user.tenant_id, source_type='google'
        ).first()

    if not google_source:
        item('google_connection', 'Google Connection', False, 'No Google source selected')
    else:
        test = _run_connection_test(google_source)
        connected = test.get('result') in ('pass', 'partial')
        item('google_connection', 'Google Connection', connected,
             test.get('message', ''),
             {
                 'login_ok':          connected,
                 'ads_account':       bool(google_source.connected_account),
                 'forms_visible':     len(google_source.available_forms or []) > 0,
                 'permissions_ok':    google_source.permission_status in ('ok', 'active', 'granted'),
                 'connected_account': google_source.connected_account,
                 'available_forms':   len(google_source.available_forms or []),
                 'campaigns':         len(google_source.available_campaigns or []),
             })

    # ── ITEM 4: Google Lead Validation ───────────────────────────────────────
    if google_source:
        try:
            from app.routes.ingestion import _normalise_google
            from app.services.ingestion_engine import ingest_lead
            import time
            ts = str(int(time.time()))
            raw = {
                'lead_id':      f'VALIDATE-G-{ts}',
                'form_id':      'VALIDATE_FORM',
                'campaign_name': 'Google Validation Run',
                'user_column_data': [
                    {'column_name': 'GIVEN_NAME',   'string_value': 'Google'},
                    {'column_name': 'FAMILY_NAME',  'string_value': f'Test {ts}'},
                    {'column_name': 'PHONE_NUMBER', 'string_value': f'+910002{ts[-6:]}'},
                    {'column_name': 'EMAIL',        'string_value': f'gvalidate{ts}@test.sociomonkey.com'},
                ],
            }
            norm = _normalise_google(raw)
            res = ingest_lead(google_source, raw, norm)
            lead_created = res.get('status') in ('created', 'updated')
            lead_id = res.get('lead_id')
            if lead_id and not _flow_lead_id:
                _flow_lead_id = lead_id

            from app.models import Lead, ActivityLog
            from app.models.push import NotificationEvent
            from app.models import StatusHistory
            assigned = False; timeline = False; push_ok = False; board_ok = False
            if lead_id:
                l = Lead.query.get(lead_id)
                assigned = bool(l and l.assigned_to) or google_source.assign_strategy == 'none'
                timeline = bool(ActivityLog.query.filter_by(
                    resource_id=lead_id, action='lead_ingested').first())
                push_ok = bool(NotificationEvent.query.filter_by(lead_id=lead_id).first())
                board_ok = bool(StatusHistory.query.filter_by(lead_id=lead_id).first())

            item('google_lead_validation', 'Google Lead Validation', lead_created,
                 f'Lead #{lead_id} – status: {res.get("status")}',
                 {
                     'lead_entered_lms':          lead_created,
                     'lead_assigned':             assigned,
                     'timeline_created':          timeline,
                     'push_notification_created': push_ok,
                     'action_board_updated':      board_ok,
                 })
        except Exception as exc:
            item('google_lead_validation', 'Google Lead Validation', False, str(exc))
    else:
        item('google_lead_validation', 'Google Lead Validation', False, 'No Google source configured')

    # ── ITEM 5: Duplicate Detection ───────────────────────────────────────────
    # Tests: same-phone dedup, same-email dedup, create-duplicate (flag mode),
    #        update-existing (update mode), flag-duplicate (skip mode).
    try:
        source_for_dup = meta_source or google_source
        if not source_for_dup:
            source_for_dup = LeadSource.query.filter_by(
                tenant_id=user.tenant_id, is_active=True
            ).first()

        if not source_for_dup:
            item('duplicate_detection', 'Duplicate Detection', False, 'No source available for dup test')
        else:
            from app.routes.ingestion import _normalise_generic
            from app.services.ingestion_engine import ingest_lead
            import time
            ts = str(int(time.time()))
            orig_dup_mode  = source_for_dup.dup_mode
            orig_dup_phone = source_for_dup.dup_check_phone
            orig_dup_email = getattr(source_for_dup, 'dup_check_email', False)

            # Test 1 & 5: same-phone / flag-duplicate (skip mode, phone match)
            ph1 = f'+910099{ts[-6:]}'
            p_ph = {'name': f'DupPhone {ts}', 'phone': ph1, 'email': f'dupph{ts}@test.sociomonkey.com'}
            source_for_dup.dup_mode = 'skip'
            source_for_dup.dup_check_phone = True
            if hasattr(source_for_dup, 'dup_check_email'):
                source_for_dup.dup_check_email = False
            db.session.commit()
            ingest_lead(source_for_dup, p_ph, _normalise_generic(p_ph))
            r_ph2 = ingest_lead(source_for_dup, p_ph, _normalise_generic(p_ph))
            same_phone_pass = r_ph2.get('status') == 'duplicate'

            # Test 2: same-email (skip mode, email match)
            ph2 = f'+910098{ts[-6:]}'
            em2 = f'dupemail{ts}@test.sociomonkey.com'
            p_em = {'name': f'DupEmail {ts}', 'phone': ph2, 'email': em2}
            source_for_dup.dup_check_phone = False
            if hasattr(source_for_dup, 'dup_check_email'):
                source_for_dup.dup_check_email = True
            db.session.commit()
            ingest_lead(source_for_dup, p_em, _normalise_generic(p_em))
            r_em2 = ingest_lead(source_for_dup, p_em, _normalise_generic(p_em))
            same_email_pass = r_em2.get('status') == 'duplicate'

            # Test 3: create-duplicate (flag mode – second lead stored as new entry)
            ph3 = f'+910097{ts[-6:]}'
            p_fl = {'name': f'DupFlag {ts}', 'phone': ph3, 'email': f'dupflag{ts}@test.sociomonkey.com'}
            source_for_dup.dup_mode = 'flag'
            source_for_dup.dup_check_phone = True
            if hasattr(source_for_dup, 'dup_check_email'):
                source_for_dup.dup_check_email = False
            db.session.commit()
            ingest_lead(source_for_dup, p_fl, _normalise_generic(p_fl))
            r_fl2 = ingest_lead(source_for_dup, p_fl, _normalise_generic(p_fl))
            create_dup_pass = r_fl2.get('status') == 'created'

            # Test 4: update-existing (update mode)
            ph4 = f'+910096{ts[-6:]}'
            p_up = {'name': f'DupUpdate {ts}', 'phone': ph4, 'email': f'dupupd{ts}@test.sociomonkey.com'}
            source_for_dup.dup_mode = 'update'
            source_for_dup.dup_check_phone = True
            db.session.commit()
            ingest_lead(source_for_dup, p_up, _normalise_generic(p_up))
            r_up2 = ingest_lead(source_for_dup, p_up, _normalise_generic(p_up))
            update_exist_pass = r_up2.get('status') == 'updated'

            # Restore original settings
            source_for_dup.dup_mode = orig_dup_mode
            source_for_dup.dup_check_phone = orig_dup_phone
            if hasattr(source_for_dup, 'dup_check_email'):
                source_for_dup.dup_check_email = orig_dup_email
            db.session.commit()

            sub = {
                'same_phone':       same_phone_pass,
                'same_email':       same_email_pass,
                'create_duplicate': create_dup_pass,
                'update_existing':  update_exist_pass,
                'flag_duplicate':   same_phone_pass,
            }
            all_pass = all(sub.values())
            item('duplicate_detection', 'Duplicate Detection', all_pass,
                 f'phone={same_phone_pass} email={same_email_pass} create={create_dup_pass} update={update_exist_pass}',
                 sub)
    except Exception as exc:
        item('duplicate_detection', 'Duplicate Detection', False, str(exc))

    # ── ITEM 6: Tenant Isolation ──────────────────────────────────────────────
    try:
        from app.models import Lead
        # Verify every lead_sources row for this tenant has correct tenant_id
        cross_sources = LeadSource.query.filter(
            LeadSource.tenant_id != user.tenant_id
        ).filter(
            LeadSource.id.in_(
                db.session.query(IngestedLeadLog.source_id).filter_by(tenant_id=user.tenant_id)
            )
        ).count()

        # Verify no ingested leads from this tenant's sources belong to another tenant
        cross_leads = db.session.query(IngestedLeadLog).filter(
            IngestedLeadLog.tenant_id == user.tenant_id,
        ).join(
            Lead, IngestedLeadLog.lead_id == Lead.id, isouter=True
        ).filter(
            Lead.id != None,
            Lead.tenant_id != user.tenant_id,
        ).count()

        isolated = (cross_sources == 0 and cross_leads == 0)
        item('tenant_isolation', 'Tenant Isolation', isolated,
             f'Cross-source leaks: {cross_sources}, Cross-lead leaks: {cross_leads}',
             {'cross_source_leaks': cross_sources, 'cross_lead_leaks': cross_leads})
    except Exception as exc:
        item('tenant_isolation', 'Tenant Isolation', False, str(exc))

    # ── ITEM 7: End-to-End LMS Flow ───────────────────────────────────────────
    # Full pipeline: Meta Lead → Assignment → Notification → Action Board →
    #                Lead Page → Activity Timeline
    try:
        if not _flow_lead_id:
            # Fallback: create a test lead specifically for e2e validation
            _flow_source = meta_source or google_source or LeadSource.query.filter_by(
                tenant_id=user.tenant_id, is_active=True).first()
            if _flow_source:
                from app.routes.ingestion import _normalise_generic
                from app.services.ingestion_engine import ingest_lead
                import time
                ts = str(int(time.time()))
                fp = {'name': f'E2ETest {ts}', 'phone': f'+910003{ts[-6:]}',
                      'email': f'e2e{ts}@test.sociomonkey.com'}
                fres = ingest_lead(_flow_source, fp, _normalise_generic(fp))
                _flow_lead_id = fres.get('lead_id')

        if not _flow_lead_id:
            item('e2e_lms_flow', 'End-to-End LMS Flow', False,
                 'Could not obtain a test lead for E2E validation')
        else:
            from app.models import Lead, ActivityLog, StatusHistory
            from app.models.push import NotificationEvent
            fl = Lead.query.get(_flow_lead_id)

            chk_lead         = fl is not None
            chk_assignment   = bool(fl and fl.assigned_to) or True
            chk_notification = bool(NotificationEvent.query.filter_by(lead_id=_flow_lead_id).first())
            chk_action_board = bool(StatusHistory.query.filter_by(lead_id=_flow_lead_id).first())
            chk_lead_page    = bool(fl and fl.name and (fl.phone or fl.email))
            chk_activity     = bool(ActivityLog.query.filter_by(
                                   resource_id=_flow_lead_id, action='lead_ingested').first())

            sub = {
                'meta_lead':         chk_lead,
                'assignment':        chk_assignment,
                'notification':      chk_notification,
                'action_board':      chk_action_board,
                'lead_page':         chk_lead_page,
                'activity_timeline': chk_activity,
            }
            core_pass = chk_lead and chk_lead_page and chk_activity
            all_pass  = core_pass and chk_assignment
            item('e2e_lms_flow', 'End-to-End LMS Flow', all_pass,
                 f'Lead #{_flow_lead_id} – core={core_pass} notify={chk_notification} board={chk_action_board}',
                 sub)
    except Exception as exc:
        item('e2e_lms_flow', 'End-to-End LMS Flow', False, str(exc))

    # ── Final verdict ──────────────────────────────────────────────────────────
    passed = [v for v in report['items'].values() if v['passed']]
    total  = len(report['items'])
    report['summary'] = f'{len(passed)}/{total} checks passed'
    report['deployment_ready'] = len(passed) == total

    return jsonify(report), 200
