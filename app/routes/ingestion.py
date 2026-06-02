"""
Lead Ingestion Webhook Routes
==============================
Public-facing inbound endpoints.  No user auth – verified by HMAC / platform
tokens instead.

Routes:
  GET  /api/ingestion/meta/verify/<token>     – Meta webhook verification challenge
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
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.models.base import db
from app.models.ingestion import LeadSource
from app.services.ingestion_engine import ingest_lead

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


def _load_source(source_type: str, token: str) -> LeadSource | None:
    return LeadSource.query.filter_by(
        source_type=source_type,
        webhook_token=token,
        is_active=True,
    ).first()


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

    return {
        'platform_lead_id': str(entry.get('leadgen_id', '')),
        'page_id':          str(entry.get('page_id', '')),
        'form_id':          str(entry.get('form_id', '')),
        'ad_id':            str(entry.get('ad_id', '')),
        'ad_set_id':        str(entry.get('adset_id', '')),
        'campaign_id':      str(entry.get('campaign_id', '')),
        # LMS fields
        'name':             name,
        'phone':            phone,
        'email':            field_data.get('email', '').strip(),
        'city':             city,
        # Pass raw field_data as extra so field_mapping can pick up custom fields
        'raw_fields':       field_data,
    }


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
        'form_id':          str(payload.get('form_id', '')),
        'form_name':        str(payload.get('form_name', '')),
        'campaign_id':      str(payload.get('campaign_id', '')),
        'campaign_name':    str(payload.get('campaign_name', '')),
        'ad_set_id':        str(payload.get('ad_group_id', '')),
        'ad_set_name':      str(payload.get('ad_group_name', '')),
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
        'form_id':          pick('form_id', 'form_name'),
        'campaign_id':      pick('campaign_id', 'utm_campaign'),
        'campaign_name':    pick('campaign_name', 'utm_campaign'),
        'ad_id':            pick('ad_id', 'utm_medium'),
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


@ingestion_bp.route('/meta/<token>', methods=['POST'])
def meta_webhook(token):
    """
    Receive Meta Lead Ads webhook delivery.
    Meta signs payloads with X-Hub-Signature-256 header.
    One HTTP request may carry multiple lead entries.
    """
    source = _load_source('meta', token)
    if not source:
        return jsonify({'error': 'Unknown source'}), 404

    raw_body = request.get_data()
    sig = request.headers.get('X-Hub-Signature-256', '')
    app_secret = (source.credentials or {}).get('app_secret', source.webhook_secret)

    # Verify HMAC (skip only when app_secret is not yet configured – dev mode)
    if app_secret and sig:
        if not _verify_hmac(app_secret, raw_body, sig):
            logger.warning('meta_webhook: HMAC mismatch for source %d', source.id)
            return jsonify({'error': 'Invalid signature'}), 403

    payload = request.get_json(force=True, silent=True) or {}
    results = []

    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            if change.get('field') != 'leadgen':
                continue
            lead_entry = change.get('value', {})
            normalised = _normalise_meta(lead_entry)
            normalised['page_id'] = str(entry.get('id', ''))
            result = ingest_lead(source, lead_entry, normalised)
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
