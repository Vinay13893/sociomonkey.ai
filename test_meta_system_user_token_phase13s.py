"""Phase 13s: _test_meta must not misreport a Business System User token
as "missing permissions".

A System User access token (Meta's recommended credential for server-side
integrations - doesn't expire, isn't tied to anyone's personal login
session) has no OAuth consent-scope list the way a personal login token
does, so /me/permissions legitimately comes back empty for one even
though the token works fine for everything we actually need (listing
pages, forms, and pulling leads). Before this fix, an empty permissions
response made _test_meta report permission_status='missing', which would
have shown a working System User connection as broken in the Lead
Sources UI.
"""

import io
import json
from unittest.mock import patch


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fake_urlopen_factory(me_permissions_empty):
    def _fake_urlopen(request, timeout=10):
        url = request.full_url if hasattr(request, 'full_url') else str(request)
        if 'me/permissions' in url:
            return _FakeResponse({'data': [] if me_permissions_empty else [
                {'permission': 'pages_show_list', 'status': 'granted'},
                {'permission': 'leads_retrieval', 'status': 'granted'},
            ]})
        if 'me/accounts' in url:
            return _FakeResponse({'data': [{'id': '123', 'name': 'Test Page'}]})
        if url.startswith('https://graph.facebook.com/v25.0/me?'):
            return _FakeResponse({'id': '999', 'name': 'Sociomonkey System User'})
        return _FakeResponse({'data': []})
    return _fake_urlopen


def _make_source():
    from app.models.ingestion import LeadSource

    return LeadSource(
        id=1,
        tenant_id=1,
        name='Meta - System User Test',
        source_type='meta',
        credentials={'user_token': 'fake-system-user-token'},
        available_forms=[],
    )


def test_system_user_style_token_reports_ok_not_missing():
    from app import create_app
    from app.routes.lead_sources import _test_meta

    app = create_app('testing')
    with app.app_context():
        source = _make_source()
        with patch('urllib.request.urlopen', side_effect=_fake_urlopen_factory(me_permissions_empty=True)):
            result = _test_meta(source)

        assert result['result'] == 'pass'
        assert result['permission_status'] == 'ok'
        assert result['permission_details']['missing'] == []
        assert 'Business System User' in result['message']


def test_normal_oauth_token_with_granted_scopes_still_works():
    from app import create_app
    from app.routes.lead_sources import _test_meta

    app = create_app('testing')
    with app.app_context():
        source = _make_source()
        with patch('urllib.request.urlopen', side_effect=_fake_urlopen_factory(me_permissions_empty=False)):
            result = _test_meta(source)

        assert result['permission_status'] in ('ok', 'partial')
        assert 'Business System User' not in result['message']
