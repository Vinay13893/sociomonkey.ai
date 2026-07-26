"""Phase 13p: GET /api/visits/export - Excel export for the Channel
Partner "Meetings" list, matching whatever filters (participant_type,
status, assigned_user_id, date range) the on-screen list currently uses.
"""


def _seed_capabilities(db, tenant_id):
    from app.models.organisation import BusinessRole, PermissionDefinition, RolePermission

    perm = PermissionDefinition.query.filter_by(key='visits.view').first()
    if not perm:
        perm = PermissionDefinition(key='visits.view', module='visits', action='VIEW')
        db.session.add(perm)
        db.session.flush()
    role = BusinessRole.query.filter_by(tenant_id=tenant_id, key='SALES_MANAGER').first()
    if not role:
        role = BusinessRole(tenant_id=tenant_id, key='SALES_MANAGER', display_name='Sales Manager', is_system=True)
        db.session.add(role)
        db.session.flush()
    from app.models.organisation import UserBusinessRole  # noqa: F401 (imported for clarity at call site)
    db.session.add(RolePermission(
        tenant_id=tenant_id, business_role_id=role.id, permission_id=perm.id,
        scope_type='TENANT', effect='ALLOW',
    ))
    db.session.flush()
    return role


def _bootstrap(app):
    from app.models.base import db
    from app.models.channel_partner import ChannelPartner
    from app.models.organisation import UserBusinessRole
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import Visit, VisitParticipant
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='Visits Export Tenant', slug='visits-export-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))
    role = _seed_capabilities(db, tenant.id)

    manager = User(
        name='Manager', email='visitexport-mgr@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
    )
    db.session.add(manager)
    db.session.flush()
    db.session.add(UserBusinessRole(
        tenant_id=tenant.id, user_id=manager.id, business_role_id=role.id, is_primary=True,
    ))

    partner = ChannelPartner(
        tenant_id=tenant.id, code='CPEXP', partner_type='INDIVIDUAL', name='Export Partner',
        created_by=manager.id, updated_by=manager.id,
    )
    db.session.add(partner)
    db.session.flush()

    visit = Visit(
        tenant_id=tenant.id, visit_type_key='MEETING', status_key='SCHEDULED',
        assigned_user_id=manager.id, purpose='Exportable meeting',
        created_by=manager.id, updated_by=manager.id,
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
    return tenant, headers


def test_export_visits_returns_xlsx():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/visits/export?participant_type=CHANNEL_PARTNER', headers=headers)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert resp.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert len(resp.data) > 0
