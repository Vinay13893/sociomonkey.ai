"""SQLAlchemy commit hooks that mirror changed lead rows to Google Sheets."""
import json
import logging
import os
import urllib.request

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.lead import CallbackReminder, Lead, LeadAssignmentHistory, LeadNote, StatusHistory

logger = logging.getLogger(__name__)
_REGISTERED = False


def register_google_sheets_events():
    global _REGISTERED
    if _REGISTERED:
        return
    _REGISTERED = True

    @event.listens_for(Session, 'before_flush')
    def _capture_lead_changes(session, flush_context, instances):
        changed = session.info.setdefault('google_sheet_changed_leads', {})
        for obj in set(session.new).union(session.dirty).union(session.deleted):
            tenant_id = lead_id = None
            if isinstance(obj, Lead):
                tenant_id, lead_id = obj.tenant_id, obj.id
            elif isinstance(obj, (LeadNote, CallbackReminder, StatusHistory, LeadAssignmentHistory)):
                lead_id = getattr(obj, 'lead_id', None)
                lead = getattr(obj, 'lead', None)
                tenant_id = getattr(obj, 'tenant_id', None) or getattr(lead, 'tenant_id', None)
            if tenant_id and lead_id:
                changed.setdefault(int(tenant_id), set()).add(int(lead_id))

    @event.listens_for(Session, 'after_flush')
    def _capture_new_lead_ids(session, flush_context):
        """New Lead IDs do not exist during before_flush; collect them here."""
        changed = session.info.setdefault('google_sheet_changed_leads', {})
        for obj in session.new:
            if isinstance(obj, Lead) and obj.tenant_id and obj.id:
                changed.setdefault(int(obj.tenant_id), set()).add(int(obj.id))

    @event.listens_for(Session, 'after_commit')
    def _push_lead_changes(session):
        changed = session.info.pop('google_sheet_changed_leads', {})
        backend_url = str(os.environ.get('BACKEND_URL') or '').rstrip('/')
        token = str(os.environ.get('INTERNAL_OPS_TOKEN') or '').strip()
        if not changed or not backend_url or not token:
            return
        for tenant_id, lead_ids in changed.items():
            try:
                payload = json.dumps({
                    'tenant_id': tenant_id, 'lead_ids': sorted(lead_ids),
                }).encode('utf-8')
                request = urllib.request.Request(
                    backend_url + '/api/google-sheets/internal/sync-leads',
                    data=payload, method='POST', headers={
                        'Content-Type': 'application/json',
                        'X-Internal-Ops-Token': token,
                    },
                )
                with urllib.request.urlopen(request, timeout=12):
                    pass
            except Exception as exc:
                logger.warning('google_sheet_realtime_sync_failed tenant=%s error=%s', tenant_id, exc)
