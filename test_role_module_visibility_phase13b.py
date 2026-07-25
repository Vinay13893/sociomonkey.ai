"""Integration checks for Phase 13b: GET /api/organisation/my-roles, the
self-service endpoint the frontend uses to drive per-role sidebar/module
visibility. Deliberately @require_auth only (not organisation.view), since
not every business role (Caller, Relationship Manager) is granted
organisation.view, but every authenticated user needs their own roles to
render their own sidebar.
"""


def _bootstrap(app):
    from app.models.base import db
    from app.models.organisation import BusinessRole, UserBusinessRole
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='Module Visibility Tenant', slug='modvis-tenant')
    db.session.add(tenant)
    db.session.flush()
    caller = User(
        name='Plain Caller', email='modvis-caller@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id,
        is_active=True,
    )
    unrolled = User(
        name='No Roles Yet', email='modvis-none@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id,
        is_active=True,
    )
    db.session.add_all([caller, unrolled])
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(
        tenant_id=tenant.id, product_id=product.id, status='active'
    ))
    # db.create_all() builds tables from the models only - the phase2
    # migration's raw-SQL BusinessRole seeding never runs against the
    # in-memory SQLite test database, so it must be created explicitly here
    # (mirrors test_phase7_channel_partners_integration.py's precedent).
    caller_role = BusinessRole(
        tenant_id=tenant.id, key='CALLER', display_name='Caller', is_active=True,
    )
    db.session.add(caller_role)
    db.session.flush()
    db.session.add(UserBusinessRole(
        tenant_id=tenant.id, user_id=caller.id, business_role_id=caller_role.id,
        is_primary=True,
    ))
    db.session.commit()

    def token_headers(user):
        token = create_token(
            str(user.id), user.role, tenant.id, login_context='tenant'
        )
        return {
            'Authorization': f'Bearer {token}',
            'X-Product-Slug': 'lms',
            'Content-Type': 'application/json',
        }
    return tenant, caller, unrolled, token_headers


def test_my_roles_returns_assigned_roles_without_organisation_view_capability():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, caller, unrolled, token_headers = _bootstrap(app)
        client = app.test_client()
        # No capability_decision mocking here on purpose - CALLER is not
        # granted organisation.view by the phase2 seed, so this proves the
        # endpoint is reachable purely via @require_auth for a low-privilege
        # role, not accidentally still gated behind organisation.view.
        resp = client.get('/api/organisation/my-roles', headers=token_headers(caller))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body['legacy_role'] == 'team_member'
        assert body['roles'] == ['CALLER']
        assert body['primary_role'] == 'CALLER'


def test_my_roles_returns_empty_list_for_a_user_with_no_business_role_yet():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, caller, unrolled, token_headers = _bootstrap(app)
        client = app.test_client()
        resp = client.get('/api/organisation/my-roles', headers=token_headers(unrolled))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body['roles'] == []
        assert body['primary_role'] is None
