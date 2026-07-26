"""Phase 13i: Channel Partner visibility scoped to ownership.

Channel Partners previously had zero row-level visibility filtering - any
user with the channel_partners.view capability (granted tenant-wide to
Sales Manager/Relationship Manager/Admin/Reception by phase7) saw every
partner in the tenant regardless of who actually owned the relationship.
This adds ownership-based scoping (mirroring the Lead co-ownership
visibility model in app.utils.leads._reporting_team_ids) plus the ability
to set the Sales Manager/RM owner at creation time.
"""


def _seed_channel_partner_capabilities(db, tenant_id=None):
    from app.models.organisation import BusinessRole, PermissionDefinition, RolePermission

    keys = [
        'channel_partners.view', 'channel_partners.create',
        'channel_partners.edit', 'channel_partners.assign',
    ]
    perms = {}
    for key in keys:
        perm = PermissionDefinition.query.filter_by(key=key).first()
        if not perm:
            perm = PermissionDefinition(key=key, module='channel_partners', action=key.split('.')[-1].upper())
            db.session.add(perm)
            db.session.flush()
        perms[key] = perm
    for role_key in ('SALES_MANAGER', 'RELATIONSHIP_MANAGER'):
        role = BusinessRole.query.filter_by(tenant_id=tenant_id, key=role_key).first()
        if not role:
            role = BusinessRole(tenant_id=tenant_id, key=role_key, display_name=role_key.title(), is_system=True)
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
    from app.models.channel_partner import ChannelPartner, ChannelPartnerAssignment
    from app.models.organisation import BusinessRole, UserBusinessRole
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='CP Ownership Tenant', slug='cp-ownership-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))
    _seed_channel_partner_capabilities(db, tenant.id)

    admin = User(
        name='Admin', email='cpown-admin@example.invalid',
        password_hash='x', role='superadmin', tenant_id=tenant.id, is_active=True,
    )
    manager_a = User(
        name='Manager A', email='cpown-mgra@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
    )
    manager_b = User(
        name='Manager B', email='cpown-mgrb@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
    )
    rm_under_a = User(
        name='RM Under A', email='cpown-rma@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id, is_active=True,
        manager_id=None,
    )
    db.session.add_all([admin, manager_a, manager_b, rm_under_a])
    db.session.flush()
    rm_under_a.manager_id = manager_a.id

    sm_role = BusinessRole.query.filter_by(tenant_id=tenant.id, key='SALES_MANAGER').first()
    rm_role = BusinessRole.query.filter_by(tenant_id=tenant.id, key='RELATIONSHIP_MANAGER').first()
    db.session.add(UserBusinessRole(tenant_id=tenant.id, user_id=manager_a.id, business_role_id=sm_role.id, is_primary=True))
    db.session.add(UserBusinessRole(tenant_id=tenant.id, user_id=manager_b.id, business_role_id=sm_role.id, is_primary=True))
    db.session.add(UserBusinessRole(tenant_id=tenant.id, user_id=rm_under_a.id, business_role_id=rm_role.id, is_primary=True))

    partner_a = ChannelPartner(tenant_id=tenant.id, code='CPA', partner_type='INDIVIDUAL', name='Partner Owned By A', created_by=admin.id, updated_by=admin.id)
    partner_b = ChannelPartner(tenant_id=tenant.id, code='CPB', partner_type='INDIVIDUAL', name='Partner Owned By B', created_by=admin.id, updated_by=admin.id)
    partner_via_team = ChannelPartner(tenant_id=tenant.id, code='CPT', partner_type='INDIVIDUAL', name='Partner Owned By As RM', created_by=admin.id, updated_by=admin.id)
    db.session.add_all([partner_a, partner_b, partner_via_team])
    db.session.flush()

    db.session.add(ChannelPartnerAssignment(
        tenant_id=tenant.id, channel_partner_id=partner_a.id, user_id=manager_a.id,
        assignment_type='SALES_MANAGER', assigned_by=admin.id, is_active=True,
    ))
    db.session.add(ChannelPartnerAssignment(
        tenant_id=tenant.id, channel_partner_id=partner_b.id, user_id=manager_b.id,
        assignment_type='SALES_MANAGER', assigned_by=admin.id, is_active=True,
    ))
    db.session.add(ChannelPartnerAssignment(
        tenant_id=tenant.id, channel_partner_id=partner_via_team.id, user_id=rm_under_a.id,
        assignment_type='RELATIONSHIP_MANAGER', assigned_by=admin.id, is_active=True,
    ))
    db.session.commit()

    def _headers(user):
        token = create_token(str(user.id), user.role, tenant.id, login_context='tenant')
        return {'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms', 'Content-Type': 'application/json'}

    return tenant, admin, manager_a, manager_b, rm_under_a, partner_a, partner_b, partner_via_team, _headers


def test_sales_manager_only_sees_own_channel_partners():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, admin, manager_a, manager_b, rm_under_a, partner_a, partner_b, partner_via_team, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/channel-partners?per_page=50', headers=headers(manager_a))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        names = {row['name'] for row in resp.get_json()['channel_partners']}
        # Manager A sees their own partner AND the one owned by their
        # reporting-line RM, but not Manager B's.
        assert names == {'Partner Owned By A', 'Partner Owned By As RM'}


def test_get_channel_partner_denies_non_owner():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, admin, manager_a, manager_b, rm_under_a, partner_a, partner_b, partner_via_team, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get(f'/api/channel-partners/{partner_b.id}', headers=headers(manager_a))
        assert resp.status_code == 403, resp.get_data(as_text=True)

        own = client.get(f'/api/channel-partners/{partner_a.id}', headers=headers(manager_a))
        assert own.status_code == 200


def test_admin_sees_all_channel_partners_unfiltered():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, admin, manager_a, manager_b, rm_under_a, partner_a, partner_b, partner_via_team, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/channel-partners?per_page=50', headers=headers(admin))
        assert resp.status_code == 200
        names = {row['name'] for row in resp.get_json()['channel_partners']}
        assert names == {'Partner Owned By A', 'Partner Owned By B', 'Partner Owned By As RM'}


def test_create_channel_partner_with_owner_fields_creates_assignments():
    from app import create_app
    from app.models.channel_partner import ChannelPartnerAssignment

    app = create_app('testing')
    with app.app_context():
        tenant, admin, manager_a, manager_b, rm_under_a, partner_a, partner_b, partner_via_team, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.post(
            '/api/channel-partners', headers=headers(admin),
            json={
                'partner_type': 'INDIVIDUAL', 'name': 'Brand New Partner',
                'sales_manager_id': manager_b.id,
            },
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)
        new_id = resp.get_json()['channel_partner']['id']
        assignment = ChannelPartnerAssignment.query.filter_by(
            channel_partner_id=new_id, assignment_type='SALES_MANAGER', is_active=True,
        ).first()
        assert assignment is not None and assignment.user_id == manager_b.id

        # Manager B should now see it in their own scoped list.
        listing = client.get('/api/channel-partners?per_page=50', headers=headers(manager_b))
        names = {row['name'] for row in listing.get_json()['channel_partners']}
        assert 'Brand New Partner' in names
