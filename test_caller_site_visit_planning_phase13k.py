"""Phase 13k: CALLER can open the Site Visit Planning dialog.

openSiteVisitPlanningDialog (frontend) loads /api/gallery-operations/
references and /api/visits/configuration before rendering the form - both
require gallery.view/visits.view at TENANT scope, which CALLER's phase2
seed never granted (only leads.view/leads.edit/action_board.view/
notifications.view), so a Caller got "Permission denied" trying to plan
a site visit for their own lead.
"""


def _seed_caller_capabilities(db, tenant_id):
    from app.models.organisation import BusinessRole, PermissionDefinition, RolePermission

    keys = ['gallery.view', 'visits.view']
    role = BusinessRole.query.filter_by(tenant_id=tenant_id, key='CALLER').first()
    if not role:
        role = BusinessRole(tenant_id=tenant_id, key='CALLER', display_name='Caller', is_system=True)
        db.session.add(role)
        db.session.flush()
    for key in keys:
        perm = PermissionDefinition.query.filter_by(key=key).first()
        if not perm:
            perm = PermissionDefinition(key=key, module=key.split('.')[0], action='VIEW')
            db.session.add(perm)
            db.session.flush()
        db.session.add(RolePermission(
            tenant_id=tenant_id, business_role_id=role.id, permission_id=perm.id,
            scope_type='TENANT', effect='ALLOW',
        ))
    db.session.flush()
    return role


def _bootstrap(app, grant_capabilities):
    from app.models.base import db
    from app.models.organisation import UserBusinessRole
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='Caller Visit Planning Tenant', slug='caller-visit-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))

    caller = User(
        name='Caller One', email='callervp@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id, is_active=True,
    )
    db.session.add(caller)
    db.session.flush()

    role = _seed_caller_capabilities(db, tenant.id) if grant_capabilities else None
    if grant_capabilities:
        db.session.add(UserBusinessRole(
            tenant_id=tenant.id, user_id=caller.id, business_role_id=role.id, is_primary=True,
        ))
    db.session.commit()

    token = create_token(str(caller.id), 'team_member', tenant.id, login_context='tenant')
    headers = {'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms'}
    return tenant, headers


def test_caller_without_grant_is_denied_gallery_and_visits_config():
    """Reproduces the reported bug before the fix - proves the gap is real."""
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, headers = _bootstrap(app, grant_capabilities=False)
        client = app.test_client()

        gallery_resp = client.get('/api/gallery-operations/references', headers=headers)
        assert gallery_resp.status_code == 403, gallery_resp.get_data(as_text=True)

        visits_resp = client.get('/api/visits/configuration', headers=headers)
        assert visits_resp.status_code == 403, visits_resp.get_data(as_text=True)


def test_caller_with_grant_can_open_site_visit_planning_references():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, headers = _bootstrap(app, grant_capabilities=True)
        client = app.test_client()

        gallery_resp = client.get('/api/gallery-operations/references', headers=headers)
        assert gallery_resp.status_code == 200, gallery_resp.get_data(as_text=True)

        visits_resp = client.get('/api/visits/configuration', headers=headers)
        assert visits_resp.status_code == 200, visits_resp.get_data(as_text=True)
