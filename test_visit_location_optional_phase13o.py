"""Phase 13o: Location is no longer required to create a Visit.

Admin real-usage feedback: couldn't book a Channel Partner meeting "at
the partner's office" because Location was compulsory and only listed
the tenant's own registered Locations. validate_visit_payload
(app.services.visit_builder) now accepts a missing location_id.
Reception's separate walk-in intake (app.routes.gallery_operations) has
its own independent code path and is unaffected by this relaxation.
"""


def _seed_capabilities(db, tenant_id):
    from app.models.organisation import BusinessRole, PermissionDefinition, RolePermission

    perm = PermissionDefinition.query.filter_by(key='visits.manage').first()
    if not perm:
        perm = PermissionDefinition(key='visits.manage', module='visits', action='MANAGE')
        db.session.add(perm)
        db.session.flush()
    role = BusinessRole.query.filter_by(tenant_id=tenant_id, key='SALES_MANAGER').first()
    if not role:
        role = BusinessRole(tenant_id=tenant_id, key='SALES_MANAGER', display_name='Sales Manager', is_system=True)
        db.session.add(role)
        db.session.flush()
    db.session.add(RolePermission(
        tenant_id=tenant_id, business_role_id=role.id, permission_id=perm.id,
        scope_type='TENANT', effect='ALLOW',
    ))
    db.session.flush()
    return role


def _bootstrap(app):
    from app.models.base import db
    from app.models.organisation import UserBusinessRole
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import VisitStatusConfiguration, VisitTypeConfiguration
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='Visit Location Optional Tenant', slug='visit-loc-optional-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))
    role = _seed_capabilities(db, tenant.id)

    manager = User(
        name='Manager', email='visitloc-mgr@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
    )
    db.session.add(manager)
    db.session.flush()
    db.session.add(UserBusinessRole(
        tenant_id=tenant.id, user_id=manager.id, business_role_id=role.id, is_primary=True,
    ))
    db.session.add(VisitTypeConfiguration(
        tenant_id=tenant.id, internal_key='MEETING',
        display_name='Meeting', display_order=1, updated_by=manager.id,
    ))
    db.session.add(VisitStatusConfiguration(
        tenant_id=tenant.id, internal_key='SCHEDULED',
        display_name='Scheduled', display_order=1, updated_by=manager.id,
    ))
    db.session.commit()

    token = create_token(str(manager.id), 'sales_manager', tenant.id, login_context='tenant')
    headers = {
        'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms',
        'Content-Type': 'application/json',
    }
    return tenant, headers


def test_visit_creates_without_location():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.post(
            '/api/visits', headers=headers,
            json={
                'visit_type_key': 'MEETING',
                'purpose': 'Meeting at the partner\'s office',
                'operational_metadata': {'venue_note': "At the partner's office"},
            },
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        payload = resp.get_json()['visit']
        assert payload['location_id'] is None
        assert payload['operational_metadata']['venue_note'] == "At the partner's office"
