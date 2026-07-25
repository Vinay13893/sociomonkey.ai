"""Integration checks for Phase 13a lead co-ownership: the leads.
calling_manager_id/caller_id slots (concurrent with the existing
sales_manager_id/assigned_to slots), POST /pipeline/leads/<id>/assign's new
slot-aware routing, and get_user_visible_leads seeing a lead via any of the
4 slots.
"""


def _bootstrap(app):
    from app.models.base import db
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='Coownership Tenant', slug='coown-tenant')
    db.session.add(tenant)
    db.session.flush()
    manager = User(
        name='Sales Manager', email='coown-manager@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id,
        is_active=True,
    )
    caller = User(
        name='Caller One', email='coown-caller@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id,
        is_active=True,
    )
    calling_manager = User(
        name='Calling Manager', email='coown-cm@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id,
        is_active=True,
    )
    rm = User(
        name='Relationship Manager', email='coown-rm@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id,
        is_active=True,
    )
    db.session.add_all([manager, caller, calling_manager, rm])
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(
        tenant_id=tenant.id, product_id=product.id, status='active'
    ))
    db.session.commit()
    token = create_token(
        str(manager.id), 'sales_manager', tenant.id, login_context='tenant'
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'X-Product-Slug': 'lms',
        'Content-Type': 'application/json',
    }
    return tenant, manager, caller, calling_manager, rm, headers


def _allow_all_capabilities(monkeypatch):
    """monkeypatch (not a bare module assignment) so this is auto-restored
    after each test - a permanent override here would silently disable real
    permission checks for every test file that happens to run afterward in
    the same pytest session (alphabetical execution order made this a real,
    observed failure against test_phase10/11's 403 assertions)."""
    import app.services.permissions as permissions
    import app.routes.pipeline as pipeline_routes

    decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    monkeypatch.setattr(permissions, 'capability_decision', decision)
    monkeypatch.setattr(pipeline_routes, 'capability_decision', decision)


def test_lead_to_dict_includes_all_four_owner_slots():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead

    app = create_app('testing')
    with app.app_context():
        tenant, manager, caller, calling_manager, rm, headers = _bootstrap(app)
        lead = Lead(
            tenant_id=tenant.id, name='Four Slot Lead', phone='9001110001',
            status='new', created_by=manager.id, is_active=True,
            assigned_to=rm.id, sales_manager_id=manager.id,
            calling_manager_id=calling_manager.id, caller_id=caller.id,
        )
        db.session.add(lead)
        db.session.commit()
        data = lead.to_dict()
        assert data['assigned_to'] == rm.id and data['assigned_to_name'] == rm.name
        assert data['sales_manager_id'] == manager.id and data['sales_manager_name'] == manager.name
        assert data['calling_manager_id'] == calling_manager.id
        assert data['calling_manager_name'] == calling_manager.name
        assert data['caller_id'] == caller.id and data['caller_name'] == caller.name


def test_assign_pipeline_owner_supports_all_four_slots_concurrently(monkeypatch):
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead

    app = create_app('testing')
    _allow_all_capabilities(monkeypatch)
    with app.app_context():
        tenant, manager, caller, calling_manager, rm, headers = _bootstrap(app)
        # Visible to `manager` (the authenticated user) via sales_manager_id
        # from the start, so _visible_query() can find it for every call.
        lead = Lead(
            tenant_id=tenant.id, name='Handoff Lead', phone='9001110002',
            status='new', created_by=manager.id, is_active=True,
            sales_manager_id=manager.id,
        )
        db.session.add(lead)
        db.session.commit()
        client = app.test_client()

        for slot, target, field in [
            ('calling_manager', calling_manager, 'calling_manager_id'),
            ('caller', caller, 'caller_id'),
            ('rm', rm, 'assigned_to'),
        ]:
            resp = client.post(
                f'/api/pipeline/leads/{lead.id}/assign', headers=headers,
                json={'assigned_to': target.id, 'slot': slot},
            )
            assert resp.status_code == 200, resp.get_data(as_text=True)
            assert resp.get_json()['assignment']['role_slot'] == slot

        db.session.refresh(lead)
        # Every slot landed independently - filling caller_id/assigned_to
        # never touched sales_manager_id or calling_manager_id, and vice
        # versa. This is the "true concurrent co-ownership" the handoff
        # model depends on.
        assert lead.sales_manager_id == manager.id
        assert lead.calling_manager_id == calling_manager.id
        assert lead.caller_id == caller.id
        assert lead.assigned_to == rm.id


def test_assign_pipeline_owner_defaults_to_rm_slot_for_backward_compatibility(monkeypatch):
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead

    app = create_app('testing')
    _allow_all_capabilities(monkeypatch)
    with app.app_context():
        tenant, manager, caller, calling_manager, rm, headers = _bootstrap(app)
        lead = Lead(
            tenant_id=tenant.id, name='Legacy Assign Lead', phone='9001110003',
            status='new', created_by=manager.id, is_active=True,
            sales_manager_id=manager.id,
        )
        db.session.add(lead)
        db.session.commit()
        client = app.test_client()

        # No `slot` in the payload at all - this is every pre-existing
        # caller of this endpoint (Leads table, Action Board, etc).
        resp = client.post(
            f'/api/pipeline/leads/{lead.id}/assign', headers=headers,
            json={'assigned_to': rm.id},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        db.session.refresh(lead)
        assert lead.assigned_to == rm.id
        assert lead.assigned_by == manager.id
        assert lead.calling_manager_id is None and lead.caller_id is None


def test_visible_leads_reachable_via_any_coowner_slot():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead
    from app.utils.leads import get_user_visible_leads

    app = create_app('testing')
    with app.app_context():
        tenant, manager, caller, calling_manager, rm, headers = _bootstrap(app)
        # `caller` (team_member) is only referenced via caller_id, never
        # assigned_to - must still see this lead.
        lead = Lead(
            tenant_id=tenant.id, name='Caller Slot Lead', phone='9001110004',
            status='new', created_by=manager.id, is_active=True,
            caller_id=caller.id,
        )
        db.session.add(lead)
        db.session.commit()
        visible_ids = [row.id for row in get_user_visible_leads(caller).all()]
        assert lead.id in visible_ids
