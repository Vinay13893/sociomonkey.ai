"""Phase 13l: Relationship Manager real-usage feedback - Leads list and
Action Board were undercounting a user's own visible leads relative to
Dashboard.

1. GET /api/leads: without an explicit assigned_to filter, a team_member-
   legacy user (which is what RM/Caller accounts carry) must see their
   full get_user_visible_leads() set (assigned_to OR calling_manager_id OR
   caller_id), not just assigned_to - the frontend used to force-lock this
   filter to self, which the backend then ANDed on top of the broader
   scope, silently dropping co-owned leads. This test exercises the
   backend directly (no assigned_to param) to prove the full set is
   already available once the frontend stops forcing the narrower filter.
2. GET /api/leads/action-board: a lead whose status is
   'callback_scheduled' but has no actual CallbackReminder row (e.g. the
   reminder was deleted without updating status) now surfaces in a new
   'other_active_leads' section instead of vanishing from the board
   entirely, even under All Time.
"""


def _bootstrap(app):
    from app.models.base import db
    from app.models.lead import Lead
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='RM Visibility Tenant', slug='rm-visibility-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))

    rm = User(
        name='RM One', email='rmvis@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id, is_active=True,
    )
    caller = User(
        name='Caller One', email='rmvis-caller@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id, is_active=True,
    )
    db.session.add_all([rm, caller])
    db.session.flush()

    owned_directly = Lead(
        tenant_id=tenant.id, name='Owned Directly', phone='9101110001', status='new',
        is_active=True, assigned_to=rm.id, created_by=rm.id,
    )
    co_owned_via_caller_slot = Lead(
        tenant_id=tenant.id, name='Co-owned Via Caller Slot', phone='9101110002', status='follow_up',
        is_active=True, caller_id=rm.id, created_by=caller.id,
    )
    orphaned_callback = Lead(
        tenant_id=tenant.id, name='Orphaned Callback Lead', phone='9101110003', status='callback_scheduled',
        is_active=True, assigned_to=rm.id, created_by=rm.id,
    )
    db.session.add_all([owned_directly, co_owned_via_caller_slot, orphaned_callback])
    db.session.commit()

    token = create_token(str(rm.id), 'team_member', tenant.id, login_context='tenant')
    headers = {'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms'}
    return tenant, rm, headers


def test_leads_list_shows_full_visible_set_without_forced_assigned_to():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, rm, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/leads', headers=headers)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        names = {row['name'] for row in resp.get_json()['leads']}
        assert 'Owned Directly' in names
        assert 'Co-owned Via Caller Slot' in names


def test_action_board_surfaces_orphaned_callback_scheduled_lead():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, rm, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/leads/action-board', headers=headers)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        payload = resp.get_json()
        other_names = {row['name'] for row in payload.get('other_active_leads', [])}
        assert 'Orphaned Callback Lead' in other_names
        assert payload['summary']['other_active_count'] == 1
