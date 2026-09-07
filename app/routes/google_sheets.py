"""Tenant administration and Google Sheets integration endpoints."""
from datetime import datetime, timezone
import hmac
import os

from flask import Blueprint, current_app, jsonify, request

from app import db
from app.middleware import require_capability
from app.models.activity import ActivityLog
from app.models.lead import CallbackReminder, Lead, LeadNote, StatusHistory
from app.models.tenant import Tenant
from app.services.google_sheets_sync import (
    GoogleSheetsSyncError, full_sync, get_sheet_config, save_sheet_config,
    save_apps_script_config, sync_leads, test_connection,
)
from app.utils.leads import normalize_lead_status
from app.utils.time_utils import parse_business_datetime_to_utc_naive

google_sheets_bp = Blueprint('google_sheets', __name__, url_prefix='/api/google-sheets')

MAX_FEEDBACK_ROWS = 500


def _feedback_time(value):
    if not value:
        return datetime.min
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError):
        return datetime.min


def _prepare_feedback_rows(rows):
    """Validate feedback and retain the newest row for each LMS lead."""
    latest = {}
    errors = []
    warnings = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append({'row': index, 'error': 'row must be an object'})
            continue
        raw_id = str(row.get('lms_lead_id') or '').strip()
        try:
            lead_id = int(raw_id)
        except (TypeError, ValueError):
            errors.append({'row': index, 'error': 'invalid lms_lead_id'})
            continue

        status = normalize_lead_status(row.get('stage') or row.get('status'))
        if not status:
            errors.append({
                'row': index, 'lms_lead_id': raw_id,
                'error': 'invalid stage/status',
            })
            continue

        follow_up = row.get('next_follow_up')
        follow_up_dt = None
        remarks = str(row.get('remarks') or '').strip()
        if follow_up:
            try:
                follow_up_dt = parse_business_datetime_to_utc_naive(follow_up)
            except (TypeError, ValueError):
                legacy_text = str(follow_up).strip()
                if legacy_text and not remarks:
                    remarks = legacy_text
                warnings.append({
                    'row': index, 'lms_lead_id': raw_id,
                    'warning': 'invalid next_follow_up ignored',
                })

        prepared = {
            'source_row': index,
            'lead_id': lead_id,
            'status': status,
            'stage': str(row.get('stage') or row.get('status') or '').strip(),
            'remarks': remarks,
            'next_follow_up': follow_up_dt,
            'updated_at': row.get('updated_at'),
        }
        previous = latest.get(lead_id)
        if previous is None or _feedback_time(prepared['updated_at']) >= _feedback_time(previous['updated_at']):
            latest[lead_id] = prepared
    return list(latest.values()), errors, warnings


def _callback_manager_id(lead):
    if lead.sales_manager_id:
        return lead.sales_manager_id
    if lead.assigned_user:
        return lead.assigned_user.manager_id
    return None


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


@google_sheets_bp.post('/internal/configure-apps-script')
def internal_configure_apps_script():
    """Protected production bootstrap for an Apps Script sheet mirror."""
    expected = str(os.environ.get('INTERNAL_OPS_TOKEN') or '').strip()
    provided = str(request.headers.get('X-Internal-Ops-Token') or '').strip()
    if not expected or provided != expected:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json() or {}
    tenant_id = int(data.get('tenant_id') or 0)
    if tenant_id <= 0 and data.get('tenant_slug'):
        from app.models.tenant import Tenant
        tenant = Tenant.query.filter_by(slug=str(data.get('tenant_slug')).strip()).first()
        tenant_id = int(tenant.id) if tenant else 0
    script_url = str(data.get('script_url') or '').strip()
    webhook_secret = str(data.get('webhook_secret') or '').strip()
    if tenant_id <= 0 or not script_url.startswith('https://script.google.com/macros/s/') or not webhook_secret:
        return jsonify({'error': 'tenant_id, Apps Script URL and webhook secret are required'}), 400
    save_apps_script_config(tenant_id, {
        'mode': 'apps_script', 'script_url': script_url,
        'webhook_secret': webhook_secret,
        'sheet_name': str(data.get('sheet_name') or 'Master Leads').strip(),
        'enabled': True,
    })
    try:
        verified = test_connection(tenant_id)
        synced = full_sync(tenant_id) if data.get('full_sync', True) else None
        return jsonify({'ok': True, 'verified': verified, 'sync': synced})
    except GoogleSheetsSyncError as exc:
        return jsonify({'error': str(exc)}), 400


@google_sheets_bp.post('/feedback')
def receive_feedback():
    """Apply idempotent Channel Partner sheet feedback to canonical LMS leads."""
    payload = request.get_json(silent=True) or {}
    tenant_slug = str(payload.get('tenant_slug') or '').strip().lower()
    allowed_slug = str(
        current_app.config.get('LMS_FEEDBACK_TENANT_SLUG') or 'ganga'
    ).strip().lower()
    if tenant_slug != allowed_slug:
        return jsonify({'error': 'Invalid tenant_slug'}), 400

    tenant = Tenant.query.filter_by(slug=tenant_slug).first()
    if not tenant:
        return jsonify({'error': 'Tenant not found'}), 404

    _, _, sheet_config = get_sheet_config(tenant.id)
    expected = str(
        current_app.config.get('LMS_FEEDBACK_SECRET')
        or sheet_config.get('webhook_secret')
        or ''
    ).strip()
    supplied = str(request.headers.get('X-LMS-Feedback-Secret') or '').strip()
    if not expected:
        return jsonify({'error': 'Feedback bridge is not configured'}), 503
    if not supplied or not hmac.compare_digest(expected, supplied):
        return jsonify({'error': 'Forbidden'}), 403

    rows = payload.get('rows')
    if not isinstance(rows, list):
        return jsonify({'error': 'rows must be an array'}), 400
    if len(rows) > MAX_FEEDBACK_ROWS:
        return jsonify({'error': f'rows cannot exceed {MAX_FEEDBACK_ROWS}'}), 400

    prepared, errors, warnings = _prepare_feedback_rows(rows)
    lead_ids = [row['lead_id'] for row in prepared]
    leads = {
        lead.id: lead
        for lead in Lead.query.filter(
            Lead.tenant_id == tenant.id,
            Lead.id.in_(lead_ids or [-1]),
            Lead.is_active == True,
        ).all()
    }

    remark_values = list({row['remarks'] for row in prepared if row['remarks']})
    remark_pairs = {
        (note.lead_id, note.note)
        for note in LeadNote.query.filter(
            LeadNote.lead_id.in_(lead_ids or [-1]),
            LeadNote.note.in_(remark_values or ['']),
        ).all()
    }
    pending_callbacks = {}
    for callback in CallbackReminder.query.filter(
        CallbackReminder.lead_id.in_(lead_ids or [-1]),
        CallbackReminder.status == 'pending',
    ).order_by(
        CallbackReminder.lead_id,
        CallbackReminder.callback_datetime,
        CallbackReminder.id,
    ).all():
        pending_callbacks.setdefault(callback.lead_id, callback)

    updated = 0
    unchanged = 0
    skipped_past_followups = 0
    request_time = datetime.utcnow()
    for row in prepared:
        lead = leads.get(row['lead_id'])
        if not lead:
            errors.append({
                'row': row['source_row'],
                'lms_lead_id': str(row['lead_id']),
                'error': 'active lead not found for tenant',
            })
            continue

        row_changed = False
        if lead.status != row['status']:
            old_status = lead.status
            lead.status = row['status']
            db.session.add(StatusHistory(
                lead_id=lead.id,
                old_status=old_status,
                new_status=row['status'],
                changed_by=None,
            ))
            db.session.add(ActivityLog(
                tenant_id=tenant.id,
                user_id=None,
                action='channel_partner_sheet_stage_update',
                module='leads',
                resource_id=lead.id,
                resource_type='Lead',
                old_value={'status': old_status},
                new_value={
                    'status': row['status'],
                    'sheet_stage': row['stage'],
                },
                description='Lead stage updated from Channel Partner sheet',
            ))
            row_changed = True

        remarks = row['remarks']
        if remarks and (lead.id, remarks) not in remark_pairs:
            db.session.add(LeadNote(
                lead_id=lead.id,
                note=remarks,
                created_by=None,
            ))
            remark_pairs.add((lead.id, remarks))
            row_changed = True

        follow_up_dt = row['next_follow_up']
        if follow_up_dt and follow_up_dt > request_time:
            callback = pending_callbacks.get(lead.id)
            if callback:
                if callback.callback_datetime != follow_up_dt:
                    callback.callback_datetime = follow_up_dt
                    callback.reminder_10_sent = False
                    callback.reminder_due_sent = False
                    row_changed = True
            else:
                callback = CallbackReminder(
                    lead_id=lead.id,
                    tenant_id=tenant.id,
                    assigned_user_id=lead.assigned_to,
                    manager_id=_callback_manager_id(lead),
                    callback_datetime=follow_up_dt,
                    notes=remarks or None,
                    created_by=None,
                )
                db.session.add(callback)
                pending_callbacks[lead.id] = callback
                row_changed = True
        elif follow_up_dt:
            # Historical retry must not create an already-overdue reminder.
            skipped_past_followups += 1

        if row_changed:
            lead.updated_at = datetime.utcnow()
            updated += 1
        else:
            unchanged += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Google Sheets feedback batch failed')
        return jsonify({'error': 'Feedback batch could not be committed'}), 500

    return jsonify({
        'ok': not errors,
        'received': len(rows),
        'processed': updated + unchanged,
        'updated': updated,
        'unchanged': unchanged,
        'skipped_past_followups': skipped_past_followups,
        'errors': errors,
        'warnings': warnings,
    }), 200
