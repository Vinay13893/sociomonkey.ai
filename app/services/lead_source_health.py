"""Detects lead sources whose platform OAuth token has gone invalid
(expired/revoked/password-changed session) and raises an in-app + push
alert to the tenant's admins.

Without this, a dead Meta token fails silently: webhooks keep arriving,
but the lead-detail enrichment call fails, so every inbound lead gets
logged as an ingestion error instead of becoming a Lead - and nobody
notices until someone happens to check the Lead Sources page.
"""

import json as _json
import logging
import os
import urllib.error as _urlerr
import urllib.parse as _parse
import urllib.request as _req
from datetime import datetime, timedelta

from app.models.base import db
from app.models.ingestion import LeadSource
from app.models.notification import Notification
from app.models.push import NotificationEvent
from app.models.user import User

logger = logging.getLogger(__name__)

# Health check may run as often as hourly - only re-alert about once a day
# while a source stays broken, instead of paging admins every run.
_RENOTIFY_AFTER = timedelta(hours=20)


def _debug_token_status(token, app_id, app_secret):
    """Returns (is_valid, raw_debug_data). is_valid is None if the check
    itself couldn't be performed (missing creds / network error)."""
    if not (token and app_id and app_secret):
        return None, {'error': 'missing token or app credentials'}
    url = (
        'https://graph.facebook.com/debug_token'
        f'?input_token={_parse.quote(token)}'
        f'&access_token={_parse.quote(app_id)}%7C{_parse.quote(app_secret)}'
    )
    try:
        with _req.urlopen(_req.Request(url), timeout=10) as resp:
            data = _json.loads(resp.read()).get('data', {})
        return bool(data.get('is_valid')), data
    except _urlerr.HTTPError as exc:
        try:
            return False, _json.loads(exc.read())
        except Exception:
            return False, {'error': str(exc)}
    except Exception as exc:
        return None, {'error': str(exc)}


def _notify_admins(source, reason):
    admins = User.query.filter(
        User.tenant_id == source.tenant_id,
        User.is_active == True,  # noqa: E712
        User.role.in_(['superadmin', 'sales_manager']),
    ).all()
    for admin in admins:
        db.session.add(Notification(
            tenant_id=source.tenant_id,
            user_id=admin.id,
            category='lead_source_health',
            kind='meta_token_invalid',
            title='Meta lead source disconnected',
            message=f'"{source.name}" stopped receiving leads: {reason}. Reconnect it from Lead Sources.',
            payload={'source_id': source.id, 'reason': reason},
            source='lead_source_health',
        ))
        db.session.add(NotificationEvent(
            tenant_id=source.tenant_id,
            user_id=admin.id,
            event_type='lead_source_health',
            title='Meta lead source disconnected',
            body=f'"{source.name}" stopped receiving leads. Reconnect it from Lead Sources.',
            deep_link='/lead-sources',
            payload={'source_id': source.id, 'reason': reason},
        ))


def check_lead_source_health():
    app_id = os.environ.get('META_APP_ID', '')
    app_secret = os.environ.get('META_APP_SECRET', '')

    summary = {'checked': 0, 'invalid': 0, 'notified': 0, 'recovered': 0, 'sources': []}
    sources = LeadSource.query.filter_by(source_type='meta', is_active=True).all()

    for source in sources:
        creds = source.credentials or {}
        token = str(
            creds.get('user_token') or creds.get('page_access_token') or creds.get('access_token') or ''
        ).strip()
        if not token:
            continue
        summary['checked'] += 1

        is_valid, data = _debug_token_status(token, app_id, app_secret)
        details = dict(source.permission_details or {})

        if is_valid is False:
            reason = ((data or {}).get('error') or {}).get('message') or 'Access token is no longer valid'
            summary['invalid'] += 1
            summary['sources'].append({'source_id': source.id, 'name': source.name, 'reason': reason})

            last_alert_raw = details.get('health_alert_sent_at')
            last_alert_at = None
            if last_alert_raw:
                try:
                    last_alert_at = datetime.fromisoformat(last_alert_raw)
                except ValueError:
                    last_alert_at = None
            should_notify = not last_alert_at or (datetime.utcnow() - last_alert_at) > _RENOTIFY_AFTER

            source.permission_status = 'error'
            source.last_test_result = 'fail'
            source.last_test_message = reason
            source.last_tested_at = datetime.utcnow()

            if should_notify:
                _notify_admins(source, reason)
                details['health_alert_sent_at'] = datetime.utcnow().isoformat()
                summary['notified'] += 1
            source.permission_details = details

        elif is_valid is True:
            if details.pop('health_alert_sent_at', None) is not None:
                source.permission_details = details
                summary['recovered'] += 1
            if source.permission_status == 'error':
                source.permission_status = 'ok'

    db.session.commit()
    return summary
