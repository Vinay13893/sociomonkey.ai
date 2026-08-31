"""Tenant administration and internal endpoints for Google Sheets mirroring."""
import os

from flask import Blueprint, jsonify, request

from app.middleware import require_capability
from app.services.google_sheets_sync import (
    GoogleSheetsSyncError, full_sync, get_sheet_config, save_sheet_config,
    save_apps_script_config, sync_leads, test_connection,
)

google_sheets_bp = Blueprint('google_sheets', __name__, url_prefix='/api/google-sheets')


def _tenant_id():
    return request.current_user.tenant_id


@google_sheets_bp.get('/status')
@require_capability('configuration.view', 'TENANT')
def sheet_status():
    source, _, config = get_sheet_config(_tenant_id())
    payload = {
        'google_connected': bool(source),
        'mode': config.get('mode') or ('google_oauth' if source else 'apps_script'),
        'google_source_id': source.id if source else None,
        'google_account': source.connected_account if source else None,
        'configured': bool(config.get('spreadsheet_id')),
        'enabled': bool(config.get('enabled')),
        'spreadsheet_id': config.get('spreadsheet_id') or '',
        'spreadsheet_url': (
            f'https://docs.google.com/spreadsheets/d/{config.get("spreadsheet_id")}/edit'
            if config.get('spreadsheet_id') else ''
        ),
        'sheet_name': config.get('sheet_name') or 'Master Leads',
        'script_url': config.get('script_url') or '',
        'webhook_secret_configured': bool(config.get('webhook_secret')),
    }
    return jsonify(payload)


@google_sheets_bp.put('/configuration')
@require_capability('configuration.manage', 'TENANT')
def configure_sheet():
    source, credentials, config = get_sheet_config(_tenant_id())
    data = request.get_json() or {}
    script_url = str(data.get('script_url') or '').strip()
    if script_url:
        webhook_secret = str(data.get('webhook_secret') or config.get('webhook_secret') or '').strip()
        if not script_url.startswith('https://script.google.com/macros/s/') or not webhook_secret:
            return jsonify({'error': 'A deployed Apps Script web-app URL and webhook secret are required'}), 400
        config = {
            'mode': 'apps_script', 'script_url': script_url,
            'webhook_secret': webhook_secret,
            'sheet_name': str(data.get('sheet_name') or 'Master Leads').strip(),
            'enabled': bool(data.get('enabled', True)),
        }
        save_apps_script_config(_tenant_id(), config, request.current_user.id)
        try:
            verified = test_connection(_tenant_id())
        except GoogleSheetsSyncError as exc:
            return jsonify({'error': str(exc)}), 400
        return jsonify({'ok': True, 'verified': verified})
    if not source:
        return jsonify({'error': 'Enter an Apps Script web-app URL'}), 400
    spreadsheet_id = str(data.get('spreadsheet_id') or '').strip()
    sheet_name = str(data.get('sheet_name') or 'Master Leads').strip()
    if not spreadsheet_id or not sheet_name:
        return jsonify({'error': 'spreadsheet_id and sheet_name are required'}), 400
    config.update({
        'spreadsheet_id': spreadsheet_id,
        'sheet_name': sheet_name,
        'enabled': bool(data.get('enabled', True)),
    })
    save_sheet_config(source, credentials, config)
    try:
        verified = test_connection(_tenant_id())
    except GoogleSheetsSyncError as exc:
        return jsonify({
            'error': str(exc),
            'needs_google_reauthorization': 'insufficient' in str(exc).lower() or 'permission' in str(exc).lower(),
        }), 400
    return jsonify({'ok': True, 'verified': verified})


@google_sheets_bp.post('/sync')
@require_capability('configuration.manage', 'TENANT')
def run_full_sync():
    try:
        return jsonify({'ok': True, **full_sync(_tenant_id())})
    except GoogleSheetsSyncError as exc:
        return jsonify({'error': str(exc)}), 400


@google_sheets_bp.post('/internal/sync-leads')
def internal_sync_leads():
    expected = str(os.environ.get('INTERNAL_OPS_TOKEN') or '').strip()
    provided = str(request.headers.get('X-Internal-Ops-Token') or '').strip()
    if not expected or provided != expected:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    try:
        return jsonify({'ok': True, **sync_leads(data.get('tenant_id'), data.get('lead_ids') or [])})
    except GoogleSheetsSyncError as exc:
        return jsonify({'error': str(exc)}), 400
