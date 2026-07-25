"""Integration checks for the guided Site Visit Planned dialog's backend:
move_pipeline_lead building a Visit from visit_payload, duplicate active-
planned-visit detection, callback_payload, and the plain-move regression
guard (no visit_payload => completely unaffected).
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
    tenant = Tenant(name='Site Visit Planning Tenant', slug='svp-tenant')
    db.session.add(tenant)
    db.session.flush()
    manager = User(
        name='SVP Manager', email='svp-manager@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id,
        is_active=True,
    )
    owner = User(
        name='SVP Lead Owner', email='svp-owner@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id,
        manager_id=None, is_active=True,
    )
    db.session.add_all([manager, owner])
    db.session.flush()
    owner.manager_id = manager.id
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(
        tenant_id=tenant.id, product_id=product.id, status='active'
    ))
    location = Location(
        tenant_id=tenant.id, code='SVP', name='SVP Gallery',
        location_type='SALES_GALLERY', created_by=manager.id,
        updated_by=manager.id,
    )
    db.session.add(location)
    db.session.flush()
    db.session.add(VisitTypeConfiguration(
        tenant_id=tenant.id, internal_key='SITE_VISIT',
        display_name='Site Visit', display_order=1, updated_by=manager.id,
    ))
    db.session.add(VisitStatusConfiguration(
        tenant_id=tenant.id, internal_key='SCHEDULED',
        display_name='Scheduled', display_order=1, updated_by=manager.id,
    ))
    db.session.commit()
    token = create_token(
        str(owner.id), 'team_member', tenant.id, login_context='tenant'
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'X-Product-Slug': 'lms',
        'Content-Type': 'application/json',
    }
    return tenant, manager, owner, location, headers


def _make_app_and_permissions():
    from app import create_app
    import app.services.permissions as permissions
    import app.routes.pipeline as pipeline_routes

    app = create_app('testing')
    decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    permissions.capability_decision = decision
    pipeline_routes.capability_decision = decision
    return app


def test_move_with_visit_payload_creates_scheduled_visit_and_sets_transition_visit_id():
    from app.models.base import db
    from app.models.lead import Lead
    from app.models.pipeline import PipelineTransition
    from app.models.visit import Visit

    app = _make_app_and_permissions()
    with app.app_context():
        tenant, manager, owner, location, headers = _bootstrap(app)
        lead = Lead(
            tenant_id=tenant.id, name='SVP Lead', status='new',
            phone='9001112222', source='Manual', assigned_to=owner.id,
            created_by=manager.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()

        client = app.test_client()
        resp = client.post(
            f'/api/pipeline/leads/{lead.id}/move', headers=headers,
            json={
                'to_status': 'site_visit_planned',
                'visit_payload': {
                    'location_id': location.id,
                    'visit_type_key': 'SITE_VISIT',
                    'expected_arrival': '2026-08-01T10:00:00',
                },
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body['lead']['status'] == 'site_visit_planned'
        assert body['visit']['status_key'] == 'SCHEDULED'
        assert body['visit']['lead_id'] == lead.id
        # Assignment defaults to the Lead's current owner when not explicit.
        assert body['visit']['assigned_user_id'] == owner.id

        visit = db.session.get(Visit, body['visit']['id'])
        assert visit is not None
        transition = PipelineTransition.query.filter_by(lead_id=lead.id).order_by(
            PipelineTransition.id.desc()
        ).first()
        assert transition.visit_id == visit.id


def test_duplicate_active_planned_visit_is_rejected_without_force():
    from app.models.base import db
    from app.models.lead import Lead

    app = _make_app_and_permissions()
    with app.app_context():
        tenant, manager, owner, location, headers = _bootstrap(app)
        lead = Lead(
            tenant_id=tenant.id, name='Dup SVP Lead', status='new',
            phone='9001113333', source='Manual', assigned_to=owner.id,
            created_by=manager.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()

        client = app.test_client()
        payload = {
            'to_status': 'site_visit_planned',
            'visit_payload': {
                'location_id': location.id, 'visit_type_key': 'SITE_VISIT',
            },
        }
        first = client.post(
            f'/api/pipeline/leads/{lead.id}/move', headers=headers, json=payload
        )
        assert first.status_code == 200, first.get_data(as_text=True)

        # Lead is already at site_visit_planned; the "no status change"
        # branch is hit, but the duplicate-visit guard must still apply
        # before that when a second visit_payload is submitted.
        second = client.post(
            f'/api/pipeline/leads/{lead.id}/move', headers=headers, json=payload
        )
        assert second.status_code == 409, second.get_data(as_text=True)
        assert second.get_json()['error'] == 'active_planned_visit_exists'

        # GET planned-visit reflects the same Visit for the frontend to
        # decide view-existing vs create-new before opening the dialog.
        lookup = client.get(
            f'/api/pipeline/leads/{lead.id}/planned-visit', headers=headers
        )
        assert lookup.status_code == 200
        assert lookup.get_json()['visit']['id'] == first.get_json()['visit']['id']


def test_callback_payload_creates_callback_atomically_with_the_transition():
    from app.models.base import db
    from app.models.lead import CallbackReminder, Lead

    app = _make_app_and_permissions()
    with app.app_context():
        tenant, manager, owner, location, headers = _bootstrap(app)
        lead = Lead(
            tenant_id=tenant.id, name='Callback SVP Lead', status='new',
            phone='9001114444', source='Manual', assigned_to=owner.id,
            created_by=manager.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()

        client = app.test_client()
        resp = client.post(
            f'/api/pipeline/leads/{lead.id}/move', headers=headers,
            json={
                'to_status': 'site_visit_planned',
                'visit_payload': {
                    'location_id': location.id, 'visit_type_key': 'SITE_VISIT',
                },
                'callback_payload': {
                    'callback_datetime': '2099-01-01T09:00:00',
                    'notes': 'Reminder before the site visit',
                },
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        callback = CallbackReminder.query.filter_by(lead_id=lead.id).first()
        assert callback is not None
        assert callback.notes == 'Reminder before the site visit'


def test_plain_status_move_without_visit_payload_is_unaffected():
    from app.models.base import db
    from app.models.lead import Lead
    from app.models.visit import Visit

    app = _make_app_and_permissions()
    with app.app_context():
        tenant, manager, owner, location, headers = _bootstrap(app)
        lead = Lead(
            tenant_id=tenant.id, name='Plain Move Lead', status='new',
            phone='9001115555', source='Manual', assigned_to=owner.id,
            created_by=manager.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()

        client = app.test_client()
        resp = client.post(
            f'/api/pipeline/leads/{lead.id}/move', headers=headers,
            json={'to_status': 'site_visit_planned'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body['lead']['status'] == 'site_visit_planned'
        assert body.get('visit') is None
        assert Visit.query.filter_by(tenant_id=tenant.id).count() == 0


if __name__ == '__main__':
    test_move_with_visit_payload_creates_scheduled_visit_and_sets_transition_visit_id()
    test_duplicate_active_planned_visit_is_rejected_without_force()
    test_callback_payload_creates_callback_atomically_with_the_transition()
    test_plain_status_move_without_visit_payload_is_unaffected()
    print('Pipeline site visit planning tests passed')
