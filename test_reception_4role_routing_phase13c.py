"""Integration checks for Phase 13c: Reception's explicit "assigning as"
role picker (lead_role_slot) on walk-in creation and Visit reassignment.
Legacy-role inference (sync_lead_owner_if_unset) can't disambiguate a
Caller from an RM, or a Calling Manager from a Sales Manager - an explicit
slot from the picker must route to the correct one of the 4 Lead
co-ownership fields, and must overwrite deliberately (unlike the passive
default-if-empty legacy fallback).
"""


def _bootstrap(app):
    from app.models.base import db
    from app.models.location import Location
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import VisitStatusConfiguration, VisitTypeConfiguration
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='4-Role Routing Tenant', slug='4role-tenant')
    db.session.add(tenant)
    db.session.flush()
    receptionist = User(
        name='Reception Test', email='4role-reception@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id,
        is_active=True,
    )
    db.session.add(receptionist)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(
        tenant_id=tenant.id, product_id=product.id, status='active'
    ))
    location = Location(
        tenant_id=tenant.id, code='4ROLE', name='4-Role Gallery',
        location_type='SALES_GALLERY', created_by=receptionist.id,
        updated_by=receptionist.id,
    )
    db.session.add(location)
    db.session.flush()
    db.session.add(VisitTypeConfiguration(
        tenant_id=tenant.id, internal_key='WALK_IN',
        display_name='Walk-in', display_order=1, updated_by=receptionist.id,
    ))
    for order, key in enumerate(['SCHEDULED', 'CHECKED_IN', 'COMPLETED'], 1):
        db.session.add(VisitStatusConfiguration(
            tenant_id=tenant.id, internal_key=key,
            display_name=key.title(), display_order=order,
            updated_by=receptionist.id,
        ))
    db.session.commit()
    token = create_token(
        str(receptionist.id), 'team_member', tenant.id, login_context='tenant'
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'X-Product-Slug': 'lms',
        'Content-Type': 'application/json',
    }
    return tenant, receptionist, location, headers


def _add_user(tenant, name, email):
    from app.models.base import db
    from app.models.user import User
    user = User(
        name=name, email=email, password_hash='x', role='team_member',
        tenant_id=tenant.id, is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def _make_app_and_permissions():
    from app import create_app
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    return app


def test_walk_in_with_explicit_lead_role_slot_routes_to_correct_field():
    from app.models.base import db
    from app.models.lead import Lead

    app = _make_app_and_permissions()
    with app.app_context():
        tenant, receptionist, location, headers = _bootstrap(app)
        client = app.test_client()
        calling_manager = _add_user(tenant, 'Calling Manager', '4role-cm@example.invalid')

        lead = Lead(
            tenant_id=tenant.id, name='Slot Routed Lead', phone='9002220001',
            status='new', created_by=receptionist.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()

        resp = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': lead.id,
                'assigned_user_id': calling_manager.id,
                'lead_role_slot': 'calling_manager',
                'purpose': 'Walk-in',
            },
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        db.session.refresh(lead)
        assert lead.calling_manager_id == calling_manager.id
        # No other slot touched by this explicit, single-slot choice.
        assert lead.assigned_to is None
        assert lead.sales_manager_id is None
        assert lead.caller_id is None


def test_walk_in_explicit_slot_overwrites_unlike_legacy_inference():
    from app.models.base import db
    from app.models.lead import Lead

    app = _make_app_and_permissions()
    with app.app_context():
        tenant, receptionist, location, headers = _bootstrap(app)
        client = app.test_client()
        first_caller = _add_user(tenant, 'First Caller', '4role-caller1@example.invalid')
        second_caller = _add_user(tenant, 'Second Caller', '4role-caller2@example.invalid')

        # caller_id is already set - sync_lead_owner_if_unset would never
        # touch this (only fires on an empty field), but an explicit slot
        # choice from Reception is a deliberate reassignment and must win.
        lead = Lead(
            tenant_id=tenant.id, name='Reassign Lead', phone='9002220002',
            status='new', created_by=receptionist.id, is_active=True,
            caller_id=first_caller.id,
        )
        db.session.add(lead)
        db.session.commit()

        resp = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': lead.id,
                'assigned_user_id': second_caller.id,
                'lead_role_slot': 'caller',
                'purpose': 'Walk-in',
            },
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        db.session.refresh(lead)
        assert lead.caller_id == second_caller.id


def test_walk_in_invalid_lead_role_slot_rejected():
    from app.models.base import db
    from app.models.lead import Lead

    app = _make_app_and_permissions()
    with app.app_context():
        tenant, receptionist, location, headers = _bootstrap(app)
        client = app.test_client()

        lead = Lead(
            tenant_id=tenant.id, name='Bad Slot Lead', phone='9002220003',
            status='new', created_by=receptionist.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()

        resp = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': lead.id,
                'assigned_user_id': receptionist.id,
                'lead_role_slot': 'not_a_real_slot',
                'purpose': 'Walk-in',
            },
        )
        assert resp.status_code == 400
        assert 'lead_role_slot' in resp.get_json()['error']


def test_walk_in_without_lead_role_slot_falls_back_to_legacy_inference():
    from app.models.base import db
    from app.models.lead import Lead

    app = _make_app_and_permissions()
    with app.app_context():
        tenant, receptionist, location, headers = _bootstrap(app)
        client = app.test_client()
        member = _add_user(tenant, 'Plain Member', '4role-member@example.invalid')

        lead = Lead(
            tenant_id=tenant.id, name='No Slot Lead', phone='9002220004',
            status='new', created_by=receptionist.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()

        resp = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': lead.id,
                'assigned_user_id': member.id,
                'purpose': 'Walk-in',
            },
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        db.session.refresh(lead)
        # Legacy team_member -> assigned_to, exactly as before this phase.
        assert lead.assigned_to == member.id
        assert lead.calling_manager_id is None and lead.caller_id is None


def test_assign_visit_with_explicit_lead_role_slot_routes_correctly():
    from app.models.base import db
    from app.models.lead import Lead

    app = _make_app_and_permissions()
    with app.app_context():
        tenant, receptionist, location, headers = _bootstrap(app)
        client = app.test_client()
        sales_manager = _add_user(tenant, 'Sales Manager', '4role-sm@example.invalid')

        lead = Lead(
            tenant_id=tenant.id, name='Reassignment Lead', phone='9002220005',
            status='new', created_by=receptionist.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()
        created = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': lead.id,
                'purpose': 'Walk-in',
            },
        )
        visit_id = created.get_json()['visit']['id']

        resp = client.put(
            f'/api/gallery-operations/visits/{visit_id}/assignment',
            headers=headers,
            json={'assigned_user_id': sales_manager.id, 'lead_role_slot': 'sales_manager'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        db.session.refresh(lead)
        assert lead.sales_manager_id == sales_manager.id
        assert lead.assigned_to is None
