"""Regression coverage for Meta callbacks that still use a retired URL token."""

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import patch


META_SECRET = 'test-meta-app-secret'


def _signed_payload(page_id='PAGE-1', form_id='FORM-1'):
    payload = {
        'object': 'page',
        'entry': [{
            'id': page_id,
            'changes': [{
                'field': 'leadgen',
                'value': {
                    'leadgen_id': 'LEAD-1',
                    'page_id': page_id,
                    'form_id': form_id,
                },
            }],
        }],
    }
    raw = json.dumps(payload, separators=(',', ':')).encode()
    signature = hmac.new(META_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, {'X-Hub-Signature-256': f'sha256={signature}'}


def _app_with_active_meta_source():
    from app import create_app
    from app.models.base import db
    from app.models.ingestion import LeadSource
    from app.models.tenant import Tenant

    app = create_app('testing')
    app.config['META_WEBHOOK_REQUIRE_SIGNATURE'] = True
    app.config['META_APP_SECRET'] = META_SECRET
    with app.app_context():
        db.create_all()
        tenant = Tenant(name='Ganga test', slug='ganga')
        db.session.add(tenant)
        db.session.flush()
        source = LeadSource(
            tenant_id=tenant.id,
            name='Current Meta source',
            source_type='meta',
            is_active=True,
            webhook_token='current-token',
            credentials={'page_id': 'PAGE-1'},
            available_forms=[{'id': 'FORM-1', 'name': 'Test form'}],
        )
        db.session.add(source)
        db.session.commit()
        source_id = source.id
    return app, source_id


def test_signed_retired_token_recovers_to_matching_active_source():
    app, source_id = _app_with_active_meta_source()
    raw, headers = _signed_payload()
    captured_sources = []

    def fake_capture(source, *_args, **_kwargs):
        captured_sources.append(source.id)
        return SimpleNamespace(
            status='queued', lead_id=None, dup_of_lead_id=None, id=1,
        ), True

    with patch('app.routes.ingestion.capture_ingestion_event', side_effect=fake_capture), \
            patch('app.routes.ingestion._meta_enrich_leadgen_entry', return_value={}), \
            patch('app.routes.ingestion.ingest_lead', return_value={
                'status': 'processed', 'lead_id': 123,
            }):
        response = app.test_client().post(
            '/api/ingestion/meta/retired-token',
            data=raw,
            headers=headers,
            content_type='application/json',
        )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()['ok'] is True
    assert captured_sources == [source_id]


def test_unsigned_retired_token_is_rejected():
    app, _source_id = _app_with_active_meta_source()
    raw, _headers = _signed_payload()

    response = app.test_client().post(
        '/api/ingestion/meta/retired-token',
        data=raw,
        content_type='application/json',
    )

    assert response.status_code == 404
    assert response.get_json()['error'] == 'Unknown source'


def test_signed_retired_token_with_unknown_source_identity_is_rejected():
    app, _source_id = _app_with_active_meta_source()
    raw, headers = _signed_payload(page_id='UNKNOWN-PAGE', form_id='UNKNOWN-FORM')

    response = app.test_client().post(
        '/api/ingestion/meta/retired-token',
        data=raw,
        headers=headers,
        content_type='application/json',
    )

    assert response.status_code == 404
    assert response.get_json()['error'] == 'Unknown source'
