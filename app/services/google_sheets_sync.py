"""Google Sheets mirror for tenant lead data.

The LMS remains authoritative.  Sheets is a one-way operational mirror keyed by
the immutable LMS lead ID.  Credentials are stored on the tenant's connected
Google lead source so no new database table or secret store is required.
"""
from datetime import datetime
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from sqlalchemy import func

from app import db
from app.models.ingestion import IngestedLeadLog, LeadSource
from app.models.lead import CallbackReminder, Lead, LeadNote
from app.utils.lead_attribution import latest_meta_attribution_for_leads
from app.utils.time_utils import now_ist, to_ist_str

logger = logging.getLogger(__name__)

SHEET_HEADERS = [
    'LMS Lead ID', 'Meta Lead ID', 'Created At IST', 'Updated At IST',
    'Name', 'Phone', 'Alternate Phone', 'Email', 'Project', 'Page Name',
    'Audience (Ad Set)', 'Ad Name', 'Source', 'Status', 'Sales Manager',
    'Lead Owner', 'Calling Manager', 'Caller', 'Channel Partner',
    'Latest Note', 'Next Callback IST', 'Active', 'Test Lead', 'Sheet Sync IST',
]


class GoogleSheetsSyncError(RuntimeError):
    pass


def _google_source(tenant_id):
    return (
        LeadSource.query
        .filter_by(tenant_id=tenant_id, source_type='google', is_active=True)
        .order_by(LeadSource.updated_at.desc(), LeadSource.id.desc())
        .first()
    )


def get_sheet_config(tenant_id):
    source = _google_source(tenant_id)
    if not source:
        return None, {}, {}
    credentials = dict(source.credentials or {})
    config = dict(credentials.get('sheets_sync') or {})
    return source, credentials, config


def save_sheet_config(source, credentials, config):
    credentials = dict(credentials or {})
    credentials['sheets_sync'] = dict(config or {})
    source.credentials = credentials
    db.session.add(source)
    db.session.commit()


def _request_json(url, *, access_token=None, method='GET', payload=None, timeout=30):
    headers = {'Accept': 'application/json'}
    if access_token:
        headers['Authorization'] = f'Bearer {access_token}'
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise GoogleSheetsSyncError(f'Google API {exc.code}: {detail[:500]}') from exc
    except Exception as exc:
        raise GoogleSheetsSyncError(str(exc)) from exc


def _access_token(credentials):
    client_id = str(credentials.get('client_id') or '').strip()
    client_secret = str(credentials.get('client_secret') or '').strip()
    refresh_token = str(credentials.get('refresh_token') or '').strip()
    if not all((client_id, client_secret, refresh_token)):
        raise GoogleSheetsSyncError('Google OAuth connection is incomplete')
    body = urllib.parse.urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }).encode('utf-8')
    request = urllib.request.Request(
        'https://oauth2.googleapis.com/token', data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode('utf-8'))
    except Exception as exc:
        raise GoogleSheetsSyncError(f'Google token refresh failed: {exc}') from exc
    token = str(result.get('access_token') or '').strip()
    if not token:
        raise GoogleSheetsSyncError('Google token refresh returned no access token')
    return token


def _values_url(spreadsheet_id, a1_range, suffix=''):
    encoded_range = urllib.parse.quote(a1_range, safe='')
    return (
        f'https://sheets.googleapis.com/v4/spreadsheets/{urllib.parse.quote(spreadsheet_id, safe="")}'
        f'/values/{encoded_range}{suffix}'
    )


def _latest_notes(lead_ids):
    if not lead_ids:
        return {}
    latest = (
        db.session.query(LeadNote.lead_id, func.max(LeadNote.id).label('note_id'))
        .filter(LeadNote.lead_id.in_(lead_ids)).group_by(LeadNote.lead_id).subquery()
    )
    return {
        int(row.lead_id): str(row.note or '')
        for row in LeadNote.query.join(latest, LeadNote.id == latest.c.note_id).all()
    }


def _next_callbacks(lead_ids):
    if not lead_ids:
        return {}
    rows = (
        db.session.query(
            CallbackReminder.lead_id,
            func.min(CallbackReminder.callback_datetime).label('callback_at'),
        )
        .filter(
            CallbackReminder.lead_id.in_(lead_ids),
            CallbackReminder.status == 'pending',
        )
        .group_by(CallbackReminder.lead_id).all()
    )
    return {int(row.lead_id): row.callback_at for row in rows}


def build_lead_rows(leads):
    ids = [int(lead.id) for lead in leads]
    attribution = latest_meta_attribution_for_leads(ids)
    notes = _latest_notes(ids)
    callbacks = _next_callbacks(ids)
    synced_at = now_ist().isoformat()
    rows = []
    for lead in leads:
        attr = attribution.get(int(lead.id), {})
        rows.append([
            lead.id,
            attr.get('platform_lead_id') or '',
            to_ist_str(lead.created_at) if lead.created_at else '',
            to_ist_str(lead.updated_at) if lead.updated_at else '',
            lead.name or '', lead.phone or '', lead.alternate_phone or '', lead.email or '',
            lead.project.name if lead.project else '',
            attr.get('page_name') or '', attr.get('audience') or '', attr.get('ad_name') or '',
            lead.source or '', lead.status or '',
            lead.sales_manager.name if lead.sales_manager else '',
            lead.assigned_user.name if lead.assigned_user else '',
            lead.calling_manager.name if lead.calling_manager else '',
            lead.caller.name if lead.caller else '',
            lead.channel_partner.name if lead.channel_partner else '',
            notes.get(int(lead.id), ''),
            to_ist_str(callbacks.get(int(lead.id))) if callbacks.get(int(lead.id)) else '',
            bool(lead.is_active), bool(lead.is_test), synced_at,
        ])
    return rows


def _ensure_header(access_token, spreadsheet_id, sheet_name):
    url = _values_url(spreadsheet_id, f'{sheet_name}!A1:X1', '?valueInputOption=RAW')
    _request_json(url, access_token=access_token, method='PUT', payload={
        'range': f'{sheet_name}!A1:X1', 'majorDimension': 'ROWS', 'values': [SHEET_HEADERS],
    })


def full_sync(tenant_id):
    source, credentials, config = get_sheet_config(tenant_id)
    spreadsheet_id = str(config.get('spreadsheet_id') or '').strip()
    sheet_name = str(config.get('sheet_name') or 'Master Leads').strip()
    if not source or not spreadsheet_id or not config.get('enabled'):
        raise GoogleSheetsSyncError('Google Sheet sync is not configured and enabled')
    token = _access_token(credentials)
    _ensure_header(token, spreadsheet_id, sheet_name)
    _request_json(
        _values_url(spreadsheet_id, f'{sheet_name}!A2:X', ':clear'),
        access_token=token, method='POST', payload={},
    )
    leads = (
        Lead.query.filter_by(tenant_id=tenant_id)
        .order_by(Lead.id.asc()).all()
    )
    rows = build_lead_rows(leads)
    for start in range(0, len(rows), 400):
        chunk = rows[start:start + 400]
        first_row = start + 2
        last_row = first_row + len(chunk) - 1
        target = f'{sheet_name}!A{first_row}:X{last_row}'
        _request_json(
            _values_url(spreadsheet_id, target, '?valueInputOption=RAW'),
            access_token=token, method='PUT', payload={
                'range': target, 'majorDimension': 'ROWS', 'values': chunk,
            }, timeout=45,
        )
    return {'leads_synced': len(rows), 'spreadsheet_id': spreadsheet_id, 'sheet_name': sheet_name}


def sync_leads(tenant_id, lead_ids):
    source, credentials, config = get_sheet_config(tenant_id)
    spreadsheet_id = str(config.get('spreadsheet_id') or '').strip()
    sheet_name = str(config.get('sheet_name') or 'Master Leads').strip()
    if not source or not spreadsheet_id or not config.get('enabled'):
        return {'skipped': True, 'reason': 'not_configured'}
    ids = sorted({int(value) for value in lead_ids if value})
    if not ids:
        return {'synced': 0}
    token = _access_token(credentials)
    _ensure_header(token, spreadsheet_id, sheet_name)
    existing = _request_json(
        _values_url(spreadsheet_id, f'{sheet_name}!A2:A'), access_token=token,
    ).get('values') or []
    row_by_id = {}
    for offset, row in enumerate(existing, start=2):
        if row and str(row[0]).strip().isdigit():
            row_by_id[int(row[0])] = offset
    leads = Lead.query.filter(Lead.tenant_id == tenant_id, Lead.id.in_(ids)).all()
    values_by_id = {int(lead.id): row for lead, row in zip(leads, build_lead_rows(leads))}
    append_rows = []
    for lead_id in ids:
        row = values_by_id.get(lead_id)
        if not row:
            continue
        existing_row = row_by_id.get(lead_id)
        if existing_row:
            target = f'{sheet_name}!A{existing_row}:X{existing_row}'
            _request_json(
                _values_url(spreadsheet_id, target, '?valueInputOption=RAW'),
                access_token=token, method='PUT',
                payload={'range': target, 'majorDimension': 'ROWS', 'values': [row]},
            )
        else:
            append_rows.append(row)
    if append_rows:
        _request_json(
            _values_url(
                spreadsheet_id, f'{sheet_name}!A:X',
                ':append?valueInputOption=RAW&insertDataOption=INSERT_ROWS',
            ),
            access_token=token, method='POST',
            payload={'majorDimension': 'ROWS', 'values': append_rows},
        )
    return {'synced': len(values_by_id), 'appended': len(append_rows)}


def test_connection(tenant_id):
    source, credentials, config = get_sheet_config(tenant_id)
    if not source:
        raise GoogleSheetsSyncError('Connect a Google account in Lead Sources first')
    spreadsheet_id = str(config.get('spreadsheet_id') or '').strip()
    if not spreadsheet_id:
        raise GoogleSheetsSyncError('Spreadsheet ID is not configured')
    token = _access_token(credentials)
    result = _request_json(
        f'https://sheets.googleapis.com/v4/spreadsheets/{urllib.parse.quote(spreadsheet_id, safe="")}'
        '?fields=spreadsheetId,properties.title,sheets.properties',
        access_token=token,
    )
    return {
        'spreadsheet_id': result.get('spreadsheetId'),
        'title': (result.get('properties') or {}).get('title'),
        'tabs': [((item.get('properties') or {}).get('title')) for item in result.get('sheets') or []],
    }
