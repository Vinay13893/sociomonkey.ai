"""
Lead Ingestion Webhook Routes
==============================
Public-facing inbound endpoints.  No user auth – verified by HMAC / platform
tokens instead.

Routes:
  GET  /api/ingestion/meta/verify/<token>     – Meta webhook verification challenge (legacy path, kept for compatibility)
  GET  /api/ingestion/meta/<token>            – Meta webhook verification challenge (Meta calls this on the registered callback URL itself)
  POST /api/ingestion/meta/<token>            – Meta lead-ads webhook delivery
  POST /api/ingestion/google/<token>          – Google lead form push
  POST /api/ingestion/webhook/<token>         – Generic / custom webhook
  POST /api/ingestion/<source_type>/<token>   – Catch-all for future source types

All routes call ingest_lead() from ingestion_engine which runs the shared
pipeline (field-map → dedup → assign → create → timeline → notify).
"""

import hashlib
import hmac
import json
import logging
import urllib.parse as urllib_parse
import urllib.request as urllib_req
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app

from app.models.base import db
from app.models.ingestion import LeadSource
from app.services.ingestion_engine import capture_ingestion_event, ingest_lead

logger = logging.getLogger(__name__)

ingestion_bp = Blueprint('ingestion', __name__, url_prefix='/api/ingestion')


# ── Utility ────────────────────────────────────────────────────────────────────

def _verify_hmac(secret: str, raw_body: bytes, signature_header: str) -> bool:
    """Verify SHA-256 HMAC signature. Returns True on success."""
    try:
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        # Accept both 'sha256=...' and plain hex forms
        provided = signature_header.replace('sha256=', '').strip()
        return hmac.compare_digest(expected, provided)
    except Exception:
        return False


def _verify_hmac_any(secrets: list[str], raw_body: bytes, signature_header: str) -> bool:
    """Return True when any candidate secret validates the Meta signature."""
    for secret in secrets:
        if not secret:
            continue
        if _verify_hmac(secret, raw_body, signature_header):
            return True
    return False


def _load_source(source_type: str, token: str) -> LeadSource | None:
    return LeadSource.query.filter_by(
        source_type=source_type,
        webhook_token=token,
        is_active=True,
    ).first()


def _meta_source_has_form(source: LeadSource, form_id: str) -> bool:
    if not source or not form_id:
        return False
    forms = source.available_forms or []
    target = str(form_id)
    for f in forms:
        if isinstance(f, dict):
            if str(f.get('id') or '') == target:
                return True
        elif str(f) == target:
            return True
    return False


def _resolve_meta_target_source(seed_source: LeadSource, page_id: str, form_id: str) -> LeadSource:
    """
    Resolve the active Meta source for an incoming event by page/form.
    This prevents drop-offs when Meta still calls an older token URL after reconnects.
    """
    if not seed_source:
        return seed_source

    active_sources = LeadSource.query.filter_by(
        tenant_id=seed_source.tenant_id,
        source_type='meta',
        is_active=True,
    ).order_by(LeadSource.updated_at.desc()).all()

    if not active_sources:
        return seed_source

    page_id = str(page_id or '')
    form_id = str(form_id or '')

    if page_id:
        by_page = [
            s for s in active_sources
            if str((s.credentials or {}).get('page_id') or '') == page_id
        ]
        if by_page:
            if form_id:
                for s in by_page:
                    if _meta_source_has_form(s, form_id):
                        return s
            return by_page[0]

    if form_id:
        for s in active_sources:
            if _meta_source_has_form(s, form_id):
                return s

    return active_sources[0]


def _resolve_meta_source_from_payload(payload: dict) -> LeadSource | None:
    """Resolve an active source when Meta still calls a retired token URL.

    The payload is used only to select candidate credentials. The request must
    still pass the normal Meta HMAC verification before any event is captured.
    """
    identities = []
    for entry in (payload or {}).get('entry', []) or []:
        entry_page_id = str((entry or {}).get('id') or '')
        for change in (entry or {}).get('changes', []) or []:
            if (change or {}).get('field') != 'leadgen':
                continue
            value = (change or {}).get('value') or {}
            identities.append((
                str(value.get('page_id') or entry_page_id or ''),
                str(value.get('form_id') or ''),
            ))
    if not identities:
        return None

    sources = LeadSource.query.filter_by(
        source_type='meta', is_active=True,
    ).order_by(LeadSource.updated_at.desc(), LeadSource.id.desc()).all()
    for page_id, form_id in identities:
        page_matches = [
            source for source in sources
            if page_id and str((source.credentials or {}).get('page_id') or '') == page_id
        ]
        if page_matches:
            if form_id:
                for source in page_matches:
                    if _meta_source_has_form(source, form_id):
                        return source
            return page_matches[0]
        if form_id:
            for source in sources:
                if _meta_source_has_form(source, form_id):
                    return source
    return None


# ══════════════════════════════════════════════════════════════════════════════
# META (Facebook / Instagram) NORMALIZER
# ══════════════════════════════════════════════════════════════════════════════

def _normalise_meta(entry: dict) -> dict:
    """
    Flatten one Meta lead-gen entry into canonical LMS field names.

    Meta payload shape:
    {
      "leadgen_id": "123",
      "page_id": "456",
      "form_id": "789",
      "ad_id": "...", "adset_id": "...", "campaign_id": "...",
      "field_data": [{"name": "full_name", "values": ["Ravi Kumar"]}, ...]
    }
    """
    field_data = {
        item['name'].lower(): (item.get('values') or [''])[0]
        for item in (entry.get('field_data') or [])
    }

    # Canonical name resolution for common Meta field labels
    name_candidates = [
        field_data.get('full_name'),
        field_data.get('name'),
        field_data.get('first_name', '') + ' ' + field_data.get('last_name', ''),
    ]
    name = next((v.strip() for v in name_candidates if v and v.strip()), '')

    phone_candidates = ['phone_number', 'phone', 'mobile', 'mobile_number', 'contact_number']
    phone = next((field_data.get(k, '').strip() for k in phone_candidates if field_data.get(k)), '')

    city_candidates = ['city', 'location', 'area']
    city = next((field_data.get(k, '').strip() for k in city_candidates if field_data.get(k)), '')

    def _pick_float(*keys):
        for key in keys:
            val = entry.get(key)
            if val in (None, ''):
                continue
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
        return None

    def _pick_int(*keys):
        for key in keys:
            val = entry.get(key)
            if val in (None, ''):
                continue
            try:
                return int(float(val))
            except (TypeError, ValueError):
                continue
        return None

    return {
        'platform_lead_id': str(entry.get('leadgen_id', '')),
        'platform_created_at': str(entry.get('created_time') or entry.get('created_at') or ''),
        'page_id':          str(entry.get('page_id', '')),
        'page_name':        str(entry.get('page_name', '') or entry.get('page', '') or ''),
        'form_id':          str(entry.get('form_id', '')),
        'form_name':        str(entry.get('form_name', '') or ''),
        'ad_id':            str(entry.get('ad_id', '')),
        'ad_name':          str(entry.get('ad_name', '') or ''),
        'ad_set_id':        str(entry.get('adset_id', '') or entry.get('ad_set_id', '') or ''),
        'ad_set_name':      str(entry.get('adset_name', '') or entry.get('ad_set_name', '') or ''),
        'campaign_id':      str(entry.get('campaign_id', '')),
        'campaign_name':    str(entry.get('campaign_name', '') or ''),
        'spend':            _pick_float('spend', 'amount_spent'),
        'cost_per_result':  _pick_float('cost_per_result', 'cpl'),
        'ctr':              _pick_float('ctr'),
        'cpc':              _pick_float('cpc'),
        'cpm':              _pick_float('cpm'),
        'impressions':      _pick_int('impressions'),
        'reach':            _pick_int('reach'),
        'audience':         str(entry.get('audience', '') or entry.get('target_audience', '') or ''),
        'placement':        str(entry.get('placement', '') or entry.get('placements', '') or ''),
        # LMS fields
        'name':             name,
        'phone':            phone,
        'email':            field_data.get('email', '').strip(),
        'city':             city,
        # Pass raw field_data as extra so field_mapping can pick up custom fields
        'raw_fields':       field_data,
    }


def _meta_graph_get_json(url: str, timeout: int = 12):
    with urllib_req.urlopen(urllib_req.Request(url), timeout=timeout) as resp:
        return json.loads(resp.read())


def _meta_fetch_object_name(object_id: str, token: str) -> str:
    if not object_id or not token:
        return ''
    try:
        url = (
            f'https://graph.facebook.com/v25.0/{urllib_parse.quote(str(object_id))}'
            f'?fields=id,name&access_token={urllib_parse.quote(token)}'
        )
        data = _meta_graph_get_json(url)
        if isinstance(data, dict) and data.get('error'):
            return ''
        return str((data or {}).get('name') or '').strip()
    except Exception:
        return ''


def _meta_fetch_object_name_any(object_id: str, tokens: list[str]) -> str:
    for token in tokens:
        name = _meta_fetch_object_name(object_id, token)
        if name:
            return name
    return ''


def _meta_fetch_ad_account_object_name(object_id: str, token: str, ad_account_id: str, edge_name: str) -> str:
    if not object_id or not token or not ad_account_id or not edge_name:
        return ''
    try:
        url = (
            f'https://graph.facebook.com/v25.0/act_{urllib_parse.quote(str(ad_account_id))}/{edge_name}'
            f'?fields=id,name&limit=5000&access_token={urllib_parse.quote(token)}'
        )
        data = _meta_graph_get_json(url)
        for item in (data or {}).get('data', []) or []:
            if str(item.get('id') or '') == str(object_id):
                return str(item.get('name') or '').strip()
    except Exception:
        return ''
    return ''


def _meta_fetch_ad_account_object_name_any(object_id: str, tokens: list[str], ad_account_id: str, edge_name: str) -> str:
    for token in tokens:
        name = _meta_fetch_ad_account_object_name(object_id, token, ad_account_id, edge_name)
        if name:
            return name
    return ''


def _meta_parse_float(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _meta_parse_int(value):
    if value in (None, ''):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _meta_fetch_ad_insights(ad_id: str, token: str) -> dict:
    """
    Fetch ad-level lifetime insights from Meta Graph API.
    Returns a dict with spend/ctr/cpc/cpm/reach/impressions (None when missing).
    """
    if not ad_id or not token:
        return {}

    fields = 'spend,ctr,cpc,cpm,reach,impressions'
    try:
        url = (
            f'https://graph.facebook.com/v25.0/{urllib_parse.quote(str(ad_id))}/insights'
            f'?fields={urllib_parse.quote(fields)}'
            f'&date_preset=maximum'
            f'&limit=1'
            f'&access_token={urllib_parse.quote(token)}'
        )
        payload = _meta_graph_get_json(url)
        if isinstance(payload, dict) and payload.get('error'):
            return {}

        rows = (payload or {}).get('data') or []
        if not rows:
            return {}
        row = rows[0] or {}
        return {
            'spend': _meta_parse_float(row.get('spend')),
            'ctr': _meta_parse_float(row.get('ctr')),
            'cpc': _meta_parse_float(row.get('cpc')),
            'cpm': _meta_parse_float(row.get('cpm')),
            'reach': _meta_parse_int(row.get('reach')),
            'impressions': _meta_parse_int(row.get('impressions')),
        }
    except Exception:
        return {}


def _meta_fetch_ad_insights_any(ad_id: str, tokens: list[str]) -> dict:
    for token in tokens:
        insights = _meta_fetch_ad_insights(ad_id, token)
        if insights:
            return insights
    return {}


def _meta_fetch_campaign_name(campaign_id: str, token: str) -> str:
    return _meta_fetch_object_name(campaign_id, token)


def _meta_fetch_form_name(form_id: str, token: str) -> str:
    return _meta_fetch_object_name(form_id, token)


def _meta_enrich_leadgen_entry(lead_entry: dict, source: LeadSource) -> dict:
    """
    Meta webhook sends only IDs by default. Fetch full lead detail payload so
    field_data, form name, and campaign context are available to ingestion.
    """
    creds = source.credentials or {}
    user_token = (creds.get('user_token') or '').strip()
    page_token = (creds.get('page_access_token') or creds.get('access_token') or '').strip()
    tokens = []
    for tk in (user_token, page_token):
        if tk and tk not in tokens:
            tokens.append(tk)

    token = tokens[0] if tokens else ''
    leadgen_id = str(lead_entry.get('leadgen_id') or '').strip()
    if not token:
        return {}

    try:
        lead_data = {}
        if leadgen_id:
            for tk in tokens:
                lead_url = (
                    f'https://graph.facebook.com/v25.0/{urllib_parse.quote(leadgen_id)}'
                    f'?fields=id,created_time,field_data,form_id,campaign_id,campaign_name,ad_id,ad_name,adset_id,adset_name,page_id'
                    f'&access_token={urllib_parse.quote(tk)}'
                )
                try:
                    lead_data = _meta_graph_get_json(lead_url)
                except Exception as exc:
                    logger.warning('meta_webhook: lead detail HTTP error for leadgen_id=%s: %s', leadgen_id, exc)
                    lead_data = {}
                    continue
                if isinstance(lead_data, dict) and lead_data.get('error'):
                    logger.warning('meta_webhook: lead detail fetch error for leadgen_id=%s: %s', leadgen_id, lead_data.get('error'))
                    lead_data = {}
                    continue
                if lead_data:
                    break

        form_id = str((lead_data or {}).get('form_id') or lead_entry.get('form_id') or '')
        campaign_id = str((lead_data or {}).get('campaign_id') or lead_entry.get('campaign_id') or '')
        ad_id = str((lead_data or {}).get('ad_id') or lead_entry.get('ad_id') or '')
        ad_set_id = str((lead_data or {}).get('adset_id') or lead_entry.get('adset_id') or '')
        page_id = str((lead_data or {}).get('page_id') or lead_entry.get('page_id') or '')

        # Keep the realtime path to one Graph request. Reporting enrichment and
        # spend belong to the daily reconciliation path, not webhook intake.
        ad_name = str((lead_data or {}).get('ad_name') or lead_entry.get('ad_name') or '').strip()

        ad_set_name = str((lead_data or {}).get('adset_name') or lead_entry.get('adset_name') or '').strip()

        campaign_name = str((lead_data or {}).get('campaign_name') or (lead_entry or {}).get('campaign_name') or '').strip()

        form_name = str((lead_entry or {}).get('form_name') or '').strip()
        if not form_name and form_id:
            for f in (source.available_forms or []):
                if isinstance(f, dict) and str(f.get('id') or '') == form_id:
                    form_name = str(f.get('name') or '').strip()
                    if form_name:
                        break

        page_name = str((lead_entry or {}).get('page_name') or '').strip()
        if not page_name:
            page_name = str((source.connected_account or '')).strip()

        return {
            'platform_lead_id': str((lead_data or {}).get('id') or leadgen_id or lead_entry.get('leadgen_id') or ''),
            'platform_created_at': str((lead_data or {}).get('created_time') or lead_entry.get('created_time') or lead_entry.get('created_at') or ''),
            'form_id': form_id,
            'form_name': form_name,
            'campaign_id': campaign_id,
            'campaign_name': campaign_name,
            'ad_id': ad_id,
            'ad_name': ad_name,
            'ad_set_id': ad_set_id,
            'ad_set_name': ad_set_name,
            'page_id': page_id,
            'page_name': page_name,
            'spend': lead_entry.get('spend'),
            'cost_per_result': lead_entry.get('cost_per_result') or lead_entry.get('cpl'),
            'ctr': lead_entry.get('ctr'),
            'cpc': lead_entry.get('cpc'),
            'cpm': lead_entry.get('cpm'),
            'impressions': lead_entry.get('impressions'),
            'reach': lead_entry.get('reach'),
            'audience': lead_entry.get('audience') or lead_entry.get('target_audience'),
            'placement': lead_entry.get('placement') or lead_entry.get('placements'),
            'field_data': (lead_data or {}).get('field_data') or lead_entry.get('field_data') or [],
        }
    except Exception as exc:
        logger.warning('meta_webhook: lead enrichment failed for leadgen_id=%s: %s', leadgen_id, exc)
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE LEAD FORM NORMALIZER
# ══════════════════════════════════════════════════════════════════════════════

def _normalise_google(payload: dict) -> dict:
    """
    Flatten a Google Lead Form push notification.

    Google push payload shape (Google Ads lead form webhook):
    {
      "google_key": "...",
      "lead_id": "...",
      "api_version": "2",
      "campaign_id": "...", "campaign_name": "...",
      "ad_group_id": "...", "ad_group_name": "...",
      "form_id": "...", "form_name": "...",
      "gcl_id": "...",
      "user_column_data": [
        {"column_name": "GIVEN_NAME", "string_value": "Ravi"},
        {"column_name": "FAMILY_NAME", "string_value": "Kumar"},
        {"column_name": "PHONE_NUMBER", "string_value": "+919876543210"},
        {"column_name": "EMAIL", "string_value": "ravi@example.com"},
        ...
      ]
    }
    """
    columns = {
        item['column_name'].upper(): item.get('string_value', '')
        for item in (payload.get('user_column_data') or [])
    }

    first = columns.get('GIVEN_NAME', '')
    last  = columns.get('FAMILY_NAME', '')
    name  = (first + ' ' + last).strip() or columns.get('FULL_NAME', '')

    return {
        'platform_lead_id': str(payload.get('lead_id', '')),
        'platform_created_at': str(payload.get('created_time') or payload.get('created_at') or payload.get('submission_time') or ''),
        'form_id':          str(payload.get('form_id', '')),
        'form_name':        str(payload.get('form_name', '')),
        'campaign_id':      str(payload.get('campaign_id', '')),
        'campaign_name':    str(payload.get('campaign_name', '')),
        'ad_set_id':        str(payload.get('ad_group_id', '')),
        'ad_set_name':      str(payload.get('ad_group_name', '')),
        'gclid':            str(payload.get('gclid') or payload.get('gcl_id') or ''),
        'utm_source':       str(payload.get('utm_source') or ''),
        'utm_medium':       str(payload.get('utm_medium') or ''),
        'utm_campaign':     str(payload.get('utm_campaign') or payload.get('campaign_name') or ''),
        'utm_content':      str(payload.get('utm_content') or ''),
        'utm_term':         str(payload.get('utm_term') or ''),
        'landing_page_url': str(payload.get('landing_page_url') or payload.get('page_url') or payload.get('url') or ''),
        # LMS fields
        'name':             name,
        'phone':            columns.get('PHONE_NUMBER', '').strip(),
        'email':            columns.get('EMAIL', '').strip(),
        'city':             columns.get('CITY', '').strip(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# GENERIC WEBHOOK NORMALIZER  (website forms, portals, future channels)
# ══════════════════════════════════════════════════════════════════════════════

def _normalise_generic(payload: dict) -> dict:
    """
    Best-effort normaliser for generic/custom webhooks.
    Relies on field_mapping configured in LeadSource to handle non-standard names.
    Falls back to common field name aliases automatically.
    """
    def pick(*keys):
        for k in keys:
            v = payload.get(k)
            if v and str(v).strip():
                return str(v).strip()
        return ''

    name = pick('name', 'full_name', 'first_name', 'contact_name', 'lead_name')
    if not name:
        first = pick('first_name', 'fname')
        last  = pick('last_name', 'lname')
        name  = (first + ' ' + last).strip()

    return {
        'platform_lead_id': pick('id', 'lead_id', 'form_id', 'submission_id'),
        'platform_created_at': pick('created_time', 'created_at', 'submission_time', 'timestamp'),
        'form_id':          pick('form_id', 'form_name'),
        'campaign_id':      pick('campaign_id', 'utm_campaign'),
        'campaign_name':    pick('campaign_name', 'utm_campaign'),
        'ad_id':            pick('ad_id', 'utm_medium'),
        'gclid':            pick('gclid', 'gcl_id', 'gcl_src'),
        'utm_source':       pick('utm_source', 'source'),
        'utm_medium':       pick('utm_medium'),
        'utm_campaign':     pick('utm_campaign', 'campaign_name'),
        'utm_content':      pick('utm_content'),
        'utm_term':         pick('utm_term'),
        'landing_page_url': pick('landing_page_url', 'page_url', 'url', 'landing_url'),
        # LMS fields
        'name':             name,
        'phone':            pick('phone', 'mobile', 'phone_number', 'contact'),
        'email':            pick('email', 'email_address'),
        'city':             pick('city', 'location', 'area'),
        'budget_min':       payload.get('budget_min'),
        'budget_max':       payload.get('budget_max'),
        'project_id':       payload.get('project_id'),
        'source':           pick('source', 'utm_source', 'channel'),
        # Pass everything through so custom field_mapping can pick up anything
        **{k: v for k, v in payload.items()},
    }


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE-TYPE → NORMALIZER REGISTRY
# Register new channels here – no other code changes needed
# ══════════════════════════════════════════════════════════════════════════════

_NORMALIZERS = {
    'meta':             None,    # Meta is multi-entry; handled specially below
    'google':           _normalise_google,
    'webhook':          _normalise_generic,
    'housing':          _normalise_generic,
    'magicbricks':      _normalise_generic,
    'ninetynineacres':  _normalise_generic,
    'indiamart':        _normalise_generic,
    'whatsapp_form':    _normalise_generic,
}


# ══════════════════════════════════════════════════════════════════════════════
# META ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@ingestion_bp.route('/meta/verify/<token>', methods=['GET'])
def meta_verify(token):
    """
    Meta webhook subscription verification.
    Meta sends GET with hub.challenge; we echo it back.
    """
    source = LeadSource.query.filter_by(
        source_type='meta', webhook_token=token
    ).first()
    if not source:
        return jsonify({'error': 'Unknown token'}), 404

    verify_token = (source.credentials or {}).get('verify_token', source.webhook_secret)
    hub_mode      = request.args.get('hub.mode')
    hub_challenge = request.args.get('hub.challenge')
    hub_verify    = request.args.get('hub.verify_token')

    if hub_mode == 'subscribe' and hub_verify == verify_token:
        return hub_challenge, 200, {'Content-Type': 'text/plain'}

    return jsonify({'error': 'Verification failed'}), 403


@ingestion_bp.route('/meta/<token>', methods=['GET', 'POST'])
def meta_webhook(token):
    """
    Receive Meta Lead Ads webhook delivery, or answer Meta's GET
    verification challenge sent to this same registered callback URL.
    Meta signs POST payloads with X-Hub-Signature-256 header.
    One HTTP request may carry multiple lead entries.
    """
    if request.method == 'GET':
        return meta_verify(token)

    raw_body = request.get_data()
    sig = request.headers.get('X-Hub-Signature-256', '')
    payload = request.get_json(force=True, silent=True) or {}

    source = LeadSource.query.filter_by(
        source_type='meta',
        webhook_token=token,
    ).first()
    if not source:
        # Meta keeps one callback URL at app level and may continue calling an
        # older token after a source reconnect. Recover only signed requests
        # whose page/form identifies a currently active source.
        if not sig:
            return jsonify({'error': 'Unknown source'}), 404
        source = _resolve_meta_source_from_payload(payload)
        if not source:
            return jsonify({'error': 'Unknown source'}), 404
        logger.info(
            'meta_webhook: recovered retired token using active source=%s',
            source.id,
        )

    # Build candidate secrets across current + active tenant sources so old token
    # callbacks continue to validate after reconnects/app rotations.
    candidate_secrets = [
        str(current_app.config.get('META_APP_SECRET') or '').strip(),
    ]
    primary_app_secret = (source.credentials or {}).get('app_secret', '')
    if primary_app_secret:
        candidate_secrets.append(primary_app_secret)
    if source.webhook_secret:
        candidate_secrets.append(source.webhook_secret)

    active_meta_sources = LeadSource.query.filter_by(
        tenant_id=source.tenant_id,
        source_type='meta',
        is_active=True,
    ).order_by(LeadSource.updated_at.desc()).all()

    for s in active_meta_sources:
        creds = s.credentials or {}
        app_secret = (creds.get('app_secret') or '').strip()
        if app_secret:
            candidate_secrets.append(app_secret)
        if s.webhook_secret:
            candidate_secrets.append(s.webhook_secret)

    # Preserve order, drop empties/dupes.
    seen = set()
    candidate_secrets = [
        sec for sec in candidate_secrets
        if sec and not (sec in seen or seen.add(sec))
    ]

    require_signature = bool(current_app.config.get('META_WEBHOOK_REQUIRE_SIGNATURE'))
    if require_signature and not sig:
        logger.warning('meta_webhook: missing signature for source %d', source.id)
        return jsonify({'error': 'Missing signature'}), 403
    if require_signature and not candidate_secrets:
        logger.error('meta_webhook: no signature secret configured for source %d', source.id)
        return jsonify({'error': 'Webhook signature is not configured'}), 503

    # Verify HMAC whenever Meta supplies a signature.
    if sig and candidate_secrets:
        if not _verify_hmac_any(candidate_secrets, raw_body, sig):
            logger.warning(
                'meta_webhook: HMAC mismatch for source %d (checked %d secret(s))',
                source.id,
                len(candidate_secrets),
            )
            return jsonify({'error': 'Invalid signature'}), 403

    results = []

    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            if change.get('field') != 'leadgen':
                continue
            lead_entry = change.get('value', {})
            event_page_id = str(lead_entry.get('page_id') or entry.get('id') or '')
            event_form_id = str(lead_entry.get('form_id') or '')
            target_source = _resolve_meta_target_source(source, event_page_id, event_form_id)

            captured_log, captured_new = capture_ingestion_event(
                target_source,
                lead_entry,
                platform_lead_id=str(lead_entry.get('leadgen_id') or ''),
                page_id=event_page_id,
                form_id=event_form_id,
            )
            if not captured_new and captured_log.status in ('processed', 'duplicate', 'ignored'):
                results.append({
                    'status': 'duplicate',
                    'lead_id': captured_log.lead_id or captured_log.dup_of_lead_id,
                    'log_id': captured_log.id,
                    'message': 'Provider event already processed',
                })
                continue

            if target_source and source and target_source.id != source.id:
                logger.info(
                    'meta_webhook: rerouted token_source=%s -> target_source=%s page_id=%s form_id=%s',
                    source.id,
                    target_source.id,
                    event_page_id,
                    event_form_id,
                )

            enriched = _meta_enrich_leadgen_entry(lead_entry, target_source)
            if enriched:
                # Merge enriched fields into lead entry before normalisation.
                # Field data is required for name/phone/email extraction.
                merged_entry = dict(lead_entry)
                for k, v in enriched.items():
                    if v not in (None, '', []):
                        merged_entry[k] = v
                lead_entry = merged_entry

            normalised = _normalise_meta(lead_entry)
            if not normalised.get('page_id'):
                normalised['page_id'] = str(entry.get('id', ''))
            if enriched:
                # Prefer enriched labels/IDs when available.
                for k in (
                    'campaign_id', 'campaign_name', 'form_id', 'form_name',
                    'ad_id', 'ad_name', 'ad_set_id', 'ad_set_name',
                    'spend', 'cost_per_result', 'ctr', 'cpc', 'cpm', 'impressions', 'reach',
                    'page_id', 'page_name',
                ):
                    if enriched.get(k) not in (None, '', []):
                        normalised[k] = enriched.get(k)
            result = ingest_lead(
                target_source,
                lead_entry,
                normalised,
                ingestion_log=captured_log,
            )
            results.append(result)

    return jsonify({'ok': True, 'results': results}), 200


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@ingestion_bp.route('/google/<token>', methods=['POST'])
def google_webhook(token):
    """
    Receive Google Lead Form push notification.
    Google does not sign payloads; token in URL acts as auth.
    """
    source = _load_source('google', token)
    if not source:
        return jsonify({'error': 'Unknown source'}), 404

    payload = request.get_json(force=True, silent=True) or {}

    # Google may send a batch or single object
    entries = payload if isinstance(payload, list) else [payload]
    results = []
    for entry in entries:
        normalised = _normalise_google(entry)
        result = ingest_lead(source, entry, normalised)
        results.append(result)

    return jsonify({'ok': True, 'results': results}), 200


# ══════════════════════════════════════════════════════════════════════════════
# GENERIC / CUSTOM WEBHOOK
# ══════════════════════════════════════════════════════════════════════════════

@ingestion_bp.route('/webhook/<token>', methods=['POST'])
def generic_webhook(token):
    """
    Generic webhook receiver for website forms, housing portals, custom integrations.
    Optional HMAC via X-Webhook-Signature or X-Hub-Signature-256 header.
    """
    source = _load_source('webhook', token)
    if not source:
        # Try any active source with this token (future types)
        source = LeadSource.query.filter_by(
            webhook_token=token, is_active=True
        ).first()
    if not source:
        return jsonify({'error': 'Unknown source'}), 404

    raw_body = request.get_data()
    sig = (request.headers.get('X-Webhook-Signature')
           or request.headers.get('X-Hub-Signature-256', ''))

    # Only verify HMAC if signature provided
    if sig:
        if not _verify_hmac(source.webhook_secret, raw_body, sig):
            logger.warning('generic_webhook: HMAC mismatch for source %d', source.id)
            return jsonify({'error': 'Invalid signature'}), 403

    payload = request.get_json(force=True, silent=True) or {}
    entries = payload.get('leads', payload if isinstance(payload, list) else [payload])

    normalizer = _NORMALIZERS.get(source.source_type, _normalise_generic)
    results = []
    for entry in entries:
        normalised = normalizer(entry)
        result = ingest_lead(source, entry, normalised)
        results.append(result)

    return jsonify({'ok': True, 'results': results}), 200


# ══════════════════════════════════════════════════════════════════════════════
# CATCH-ALL for future source types (housing, magicbricks, etc.)
# ══════════════════════════════════════════════════════════════════════════════

@ingestion_bp.route('/<source_type>/<token>', methods=['POST'])
def catchall_webhook(source_type, token):
    """
    Catch-all handler for any future source type.
    Uses the generic normalizer unless a specific one is registered.
    """
    source = _load_source(source_type, token)
    if not source:
        return jsonify({'error': 'Unknown source'}), 404

    payload = request.get_json(force=True, silent=True) or {}
    entries = payload if isinstance(payload, list) else [payload]

    normalizer = _NORMALIZERS.get(source_type, _normalise_generic)
    results = []
    for entry in entries:
        normalised = normalizer(entry)
        result = ingest_lead(source, entry, normalised)
        results.append(result)

    return jsonify({'ok': True, 'results': results}), 200
