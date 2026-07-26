"""Integration checks for Phase 13g: Reception's business-date filter
accepting a genuine date range (date + date_to), not just one day.
`date_to` is additive - every existing single-day caller (just `date`,
no `date_to`) must keep its exact prior behaviour.
"""
from datetime import datetime, timedelta


def _bootstrap(app):
    from app.models.base import db
    from app.models.location import Location
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import VisitStatusConfiguration, VisitTypeConfiguration
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='Date Range Tenant', slug='daterange-tenant')
    db.session.add(tenant)
    db.session.flush()
    receptionist = User(
        name='Reception Test', email='daterange-reception@example.invalid',
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
        tenant_id=tenant.id, code='DRANGE', name='Date Range Gallery',
        location_type='SALES_GALLERY', created_by=receptionist.id,
        updated_by=receptionist.id,
    )
    db.session.add(location)
    db.session.flush()
    db.session.add(VisitTypeConfiguration(
        tenant_id=tenant.id, internal_key='SITE_VISIT',
        display_name='Site Visit', display_order=1, updated_by=receptionist.id,
    ))
    db.session.add(VisitStatusConfiguration(
        tenant_id=tenant.id, internal_key='SCHEDULED',
        display_name='Scheduled', display_order=1, updated_by=receptionist.id,
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


def _make_visit(tenant, location, receptionist, expected_arrival, name_suffix):
    from app.models.base import db
    from app.models.visit import Visit

    visit = Visit(
        tenant_id=tenant.id, visit_type_key='SITE_VISIT', status_key='SCHEDULED',
        location_id=location.id, purpose=f'Range test {name_suffix}',
        expected_arrival=expected_arrival, visitor_count=1,
        created_by=receptionist.id, updated_by=receptionist.id,
    )
    db.session.add(visit)
    db.session.commit()
    return visit


def _make_app_and_permissions():
    from app import create_app
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    return app


def test_date_range_finds_visits_across_multiple_days():
    app = _make_app_and_permissions()
    with app.app_context():
        tenant, receptionist, location, headers = _bootstrap(app)
        client = app.test_client()

        today = datetime.utcnow()
        v1 = _make_visit(tenant, location, receptionist, today, 'today')
        v2 = _make_visit(tenant, location, receptionist, today + timedelta(days=2), 'plus2')
        v3 = _make_visit(tenant, location, receptionist, today + timedelta(days=5), 'plus5-outside-range')

        date_from = today.date().isoformat()
        date_to = (today + timedelta(days=3)).date().isoformat()
        resp = client.get(
            f'/api/gallery-operations/visits?view=expected&date={date_from}&date_to={date_to}',
            headers=headers,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        ids = [row['id'] for row in resp.get_json()['visits']]
        assert v1.id in ids
        assert v2.id in ids
        assert v3.id not in ids  # outside the requested range


def test_single_date_behavior_unchanged_when_date_to_omitted():
    app = _make_app_and_permissions()
    with app.app_context():
        tenant, receptionist, location, headers = _bootstrap(app)
        client = app.test_client()

        today = datetime.utcnow()
        v_today = _make_visit(tenant, location, receptionist, today, 'today')
        v_tomorrow = _make_visit(tenant, location, receptionist, today + timedelta(days=1), 'tomorrow')

        resp = client.get(
            f'/api/gallery-operations/visits?view=expected&date={today.date().isoformat()}',
            headers=headers,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        ids = [row['id'] for row in resp.get_json()['visits']]
        assert v_today.id in ids
        assert v_tomorrow.id not in ids  # single-day query, exactly as before this phase


def test_date_to_before_date_is_rejected():
    app = _make_app_and_permissions()
    with app.app_context():
        tenant, receptionist, location, headers = _bootstrap(app)
        client = app.test_client()

        today = datetime.utcnow().date().isoformat()
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
        resp = client.get(
            f'/api/gallery-operations/visits?view=expected&date={today}&date_to={yesterday}',
            headers=headers,
        )
        assert resp.status_code == 400
        assert 'date_to' in resp.get_json()['error']


def test_dashboard_summary_respects_date_range():
    app = _make_app_and_permissions()
    with app.app_context():
        tenant, receptionist, location, headers = _bootstrap(app)
        client = app.test_client()

        today = datetime.utcnow()
        _make_visit(tenant, location, receptionist, today, 'today')
        _make_visit(tenant, location, receptionist, today + timedelta(days=1), 'tomorrow')

        date_from = today.date().isoformat()
        date_to = (today + timedelta(days=1)).date().isoformat()
        resp = client.get(
            f'/api/gallery-operations/dashboard?date={date_from}&date_to={date_to}',
            headers=headers,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert resp.get_json()['summary']['expected_today'] == 2
