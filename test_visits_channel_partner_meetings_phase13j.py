"""Phase 13j: Channel Partner "Meetings" visibility.

GET /api/visits gained an opt-in participant_type filter (used by the new
Channel Partners "Meetings" tab) that additionally scopes results to the
caller's own + reporting-team assignees when participant_type is passed -
mirroring the Channel Partner ownership visibility model, and without
touching Reception's existing unrestricted TENANT-wide visit listing
(which never passes participant_type).
"""


def _seed_capabilities(db, tenant_id):
    from app.models.organisation import BusinessRole, PermissionDefinition, RolePermission

    keys = ['visits.view', 'visits.manage', 'channel_partners.view']
    perms = {}
    for key in keys:
        perm = PermissionDefinition.query.filter_by(key=key).first()
        if not perm:
            perm = PermissionDefinition(key=key, module='visits', action=key.split('.')[-1].upper())
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
    from app.models.channel_partner import ChannelPartner
    from app.models.location import Location
    from app.models.organisation import BusinessRole, UserBusinessRole
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import Visit, VisitParticipant
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='CP Meetings Tenant', slug='cp-meetings-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))
    _seed_capabilities(db, tenant.id)

    manager_a = User(
        name='Manager A', email='cpmeet-mgra@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
    )
    manager_b = User(
        name='Manager B', email='cpmeet-mgrb@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
    )
    db.session.add_all([manager_a, manager_b])
    db.session.flush()

    sm_role = BusinessRole.query.filter_by(tenant_id=tenant.id, key='SALES_MANAGER').first()
    db.session.add(UserBusinessRole(tenant_id=tenant.id, user_id=manager_a.id, business_role_id=sm_role.id, is_primary=True))
    db.session.add(UserBusinessRole(tenant_id=tenant.id, user_id=manager_b.id, business_role_id=sm_role.id, is_primary=True))

    location = Location(tenant_id=tenant.id, code='HQ', name='HQ', location_type='PROJECT', is_active=True)
    partner = ChannelPartner(
        tenant_id=tenant.id, code='CPM', partner_type='INDIVIDUAL', name='Meeting Partner',
        created_by=manager_a.id, updated_by=manager_a.id,
    )
    db.session.add_all([location, partner])
    db.session.flush()

    visit_a = Visit(
        tenant_id=tenant.id, visit_type_key='MEETING', status_key='SCHEDULED',
        location_id=location.id, assigned_user_id=manager_a.id,
        purpose='Meeting owned by A', created_by=manager_a.id, updated_by=manager_a.id,
    )
    visit_b = Visit(
        tenant_id=tenant.id, visit_type_key='MEETING', status_key='SCHEDULED',
        location_id=location.id, assigned_user_id=manager_b.id,
        purpose='Meeting owned by B', created_by=manager_b.id, updated_by=manager_b.id,
    )
    non_cp_visit = Visit(
        tenant_id=tenant.id, visit_type_key='SITE_VISIT', status_key='SCHEDULED',
        location_id=location.id, assigned_user_id=manager_a.id,
        purpose='Ordinary site visit, no CP participant', created_by=manager_a.id, updated_by=manager_a.id,
    )
    db.session.add_all([visit_a, visit_b, non_cp_visit])
    db.session.flush()
    db.session.add(VisitParticipant(
        tenant_id=tenant.id, visit_id=visit_a.id, participant_type='CHANNEL_PARTNER',
        reference_id=partner.id, display_name=partner.name, is_primary=True,
    ))
    db.session.add(VisitParticipant(
        tenant_id=tenant.id, visit_id=visit_b.id, participant_type='CHANNEL_PARTNER',
        reference_id=partner.id, display_name=partner.name, is_primary=True,
    ))
    db.session.commit()

    def _headers(user):
        token = create_token(str(user.id), user.role, tenant.id, login_context='tenant')
        return {'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms'}

    return tenant, manager_a, manager_b, _headers


def test_channel_partner_meetings_scoped_to_assignee():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, manager_a, manager_b, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/visits?participant_type=CHANNEL_PARTNER', headers=headers(manager_a))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        purposes = {row['purpose'] for row in resp.get_json()['visits']}
        assert purposes == {'Meeting owned by A'}


def test_channel_partner_meetings_include_participant_name():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, manager_a, manager_b, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/visits?participant_type=CHANNEL_PARTNER', headers=headers(manager_a))
        rows = resp.get_json()['visits']
        assert len(rows) == 1
        assert rows[0]['participant_name'] == 'Meeting Partner'


def test_unfiltered_visit_listing_is_unaffected_by_participant_scoping():
    """Reception's existing usage (no participant_type param) must stay
    exactly as unrestricted as before - the new scoping is strictly
    opt-in."""
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, manager_a, manager_b, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/visits', headers=headers(manager_a))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        purposes = {row['purpose'] for row in resp.get_json()['visits']}
        # All three visits, including manager_b's and the non-CP one - no
        # assignee filter applied when participant_type is absent.
        assert purposes == {'Meeting owned by A', 'Meeting owned by B', 'Ordinary site visit, no CP participant'}
