"""Regression coverage for the Google Sheets -> LMS feedback bridge."""
from datetime import datetime, timedelta

import pytest


SHEET_STAGE_KEYS = {
    'Interested': 'interested',
    'Not Interested': 'not_interested',
    'Callback': 'callback_scheduled',
    'No Answer': 'no_answer',
    'Busy': 'busy',
    'Switched Off': 'switched_off',
    'Invalid Number': 'invalid_number',
    'New': 'new',
    'Junk': 'junk',
    'Site Visit Planned': 'site_visit_planned',
    'Site Visit Done': 'site_visit_done',
    'Negotiation': 'negotiation',
    'Booking Done': 'booking_done',
    'Lost': 'lost',
    'Broker': 'broker',
    'Low Budget': 'low_budget',
    'Follow Up': 'follow_up',
}


@pytest.mark.parametrize('stage,status', SHEET_STAGE_KEYS.items())
def test_all_sheet_stages_normalize_to_lms_statuses(stage, status):
    from app.utils.leads import normalize_lead_status

    assert normalize_lead_status(stage) == status
    assert normalize_lead_status(status) == status


def test_feedback_route_authenticates_with_tenant_sheet_secret_and_is_idempotent():
    from app import create_app
    from app.models.activity import ActivityLog
    from app.models.base import db
    from app.models.business_configuration import BusinessRuleConfiguration
    from app.models.lead import CallbackReminder, Lead, LeadNote, StatusHistory
    from app.models.tenant import Tenant

    app = create_app('testing')
    with app.app_context():
        db.create_all()
        tenant = Tenant(name='Ganga test', slug='ganga')
        db.session.add(tenant)
        db.session.flush()
        lead = Lead(
            tenant_id=tenant.id,
            name='Feedback test lead',
            phone='9999999999',
            source='Meta',
            status='new',
            is_active=True,
        )
        db.session.add(lead)
        db.session.add(BusinessRuleConfiguration(
            tenant_id=tenant.id,
            rule_key='google_sheets_sync',
            display_name='Google Sheets Apps Script sync',
            version=1,
            definition={
                'mode': 'apps_script',
                'script_url': 'https://script.google.com/macros/s/test/exec',
                'webhook_secret': 'feedback-test-secret',
                'enabled': True,
            },
            is_active=True,
        ))
        db.session.commit()

        client = app.test_client()
        payload = {
            'tenant_slug': 'ganga',
            'rows': [{
                'lms_lead_id': str(lead.id),
                'stage': 'Busy',
                'remarks': 'Customer asked for a later call',
                'next_follow_up': (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z',
                'updated_at': datetime.utcnow().isoformat() + 'Z',
            }],
        }

        forbidden = client.post('/api/google-sheets/feedback', json=payload)
        assert forbidden.status_code == 403

        headers = {'X-LMS-Feedback-Secret': 'feedback-test-secret'}
        first = client.post('/api/google-sheets/feedback', json=payload, headers=headers)
        assert first.status_code == 200, first.get_json()
        assert first.get_json()['ok'] is True
        assert first.get_json()['updated'] == 1
        db.session.refresh(lead)
        assert lead.status == 'busy'
        assert StatusHistory.query.filter_by(lead_id=lead.id, new_status='busy').count() == 1
        assert LeadNote.query.filter_by(
            lead_id=lead.id,
            note='Customer asked for a later call',
        ).count() == 1
        assert CallbackReminder.query.filter_by(lead_id=lead.id, status='pending').count() == 1
        assert ActivityLog.query.filter_by(
            resource_id=lead.id,
            action='channel_partner_sheet_stage_update',
        ).count() == 1

        second = client.post('/api/google-sheets/feedback', json=payload, headers=headers)
        assert second.status_code == 200, second.get_json()
        assert second.get_json()['unchanged'] == 1
        assert StatusHistory.query.filter_by(lead_id=lead.id, new_status='busy').count() == 1
        assert LeadNote.query.filter_by(
            lead_id=lead.id,
            note='Customer asked for a later call',
        ).count() == 1
        assert CallbackReminder.query.filter_by(lead_id=lead.id, status='pending').count() == 1
