"""Phase 13n: Visit gained a sales_manager_id co-owner slot alongside
assigned_user_id (mirrors the Lead co-ownership model), and the Channel
Partner "Meetings" visibility scope (participant_type=CHANNEL_PARTNER on
GET /api/visits) now recognises a Sales Manager as visible-through either
owner slot, not just assigned_user_id - a Sales Manager must see a
meeting their RM is personally attending.
"""


def _seed_capabilities(db, tenant_id):
    from app.models.organisation import BusinessRole, PermissionDefinition, RolePermission

    keys = ['visits.view', 'visits.manage']
    perms = {}
    for key in keys:
        perm = PermissionDefinition.query.filter_by(key=key).first()
        if not perm:
            perm = PermissionDefinition(key=key, module='visits', action=key.split('.')[-1].upper())
            db.session.add(perm)
            db.session.flush()
        perms[key] = perm
    role = BusinessRole.query.filter_by(tenant_id=tenant_id, key='SALES_MANAGER').first()
    if not role:
        role = BusinessRole(tenant_id=tenant_id, key='SALES_MANAGER', display_name='Sales Manager', is_system=True)
        db.session.add(role)
        db.session.flush()
    for perm in perms.values():
        db.session.add(RolePermission(
            tenant_id=tenant_id, business_role_id=role.id, permission_id=perm.id,
            scope_type='TENANT', effect='ALLOW',
        ))
    db.session.flush()


def _bootstrap(app):
    from app.models.base import db
    from app.models.channel_partner import ChannelPartner
    from app.models.location import Location
    from app.models.organisation import BusinessRole, UserBusinessRole
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import Visit, VisitParticipant
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='Visit SM Owner Tenant', slug='visit-sm-owner-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))
    _seed_capabilities(db, tenant.id)

    manager = User(
        name='Manager', email='visitsm-mgr@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
    )
    rm = User(
        name='RM', email='visitsm-rm@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id, is_active=True, manager_id=None,
    )
    db.session.add_all([manager, rm])
    db.session.flush()
    rm.manager_id = manager.id
    sm_role = BusinessRole.query.filter_by(tenant_id=tenant.id, key='SALES_MANAGER').first()
    db.session.add(UserBusinessRole(
        tenant_id=tenant.id, user_id=manager.id, business_role_id=sm_role.id, is_primary=True,
    ))

    location = Location(tenant_id=tenant.id, code='HQ2', name='HQ', location_type='PROJECT', is_active=True)
    partner = ChannelPartner(
        tenant_id=tenant.id, code='CPSM', partner_type='INDIVIDUAL', name='SM Owner Partner',
        created_by=manager.id, updated_by=manager.id,
    )
    db.session.add_all([location, partner])
    db.session.flush()

    visit = Visit(
        tenant_id=tenant.id, visit_type_key='MEETING', status_key='SCHEDULED',
        location_id=location.id, assigned_user_id=rm.id, sales_manager_id=manager.id,
        purpose='RM meeting with SM as co-owner', created_by=manager.id, updated_by=manager.id,
    )
    db.session.add(visit)
    db.session.flush()
    db.session.add(VisitParticipant(
        tenant_id=tenant.id, visit_id=visit.id, participant_type='CHANNEL_PARTNER',
        reference_id=partner.id, display_name=partner.name, is_primary=True,
    ))
    db.session.commit()

    token = create_token(str(manager.id), 'sales_manager', tenant.id, login_context='tenant')
    headers = {'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms'}
    return tenant, manager, rm, visit, headers


def test_visit_serializes_sales_manager_owner():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, manager, rm, visit, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/visits/' + str(visit.id), headers=headers)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        payload = resp.get_json()['visit']
        assert payload['sales_manager_id'] == manager.id
        assert payload['sales_manager_name'] == 'Manager'


def test_sales_manager_sees_meeting_via_sales_manager_slot():
    """The Sales Manager isn't assigned_user_id on this visit (their RM
    is) - they must still see it through the sales_manager_id slot."""
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, manager, rm, visit, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/visits?participant_type=CHANNEL_PARTNER', headers=headers)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        purposes = {row['purpose'] for row in resp.get_json()['visits']}
        assert 'RM meeting with SM as co-owner' in purposes
