"""Phase 13i: 'Allocation Pending' in Management Health used to only check
assigned_to IS NULL, overstating unallocated leads for tenants using the
pre-sales co-ownership slots - a lead already picked up by a Calling
Manager/Caller but not yet handed to a final RM still counted as pending.
It should only count leads with NO owner in any of the four slots.
"""


def _bootstrap(app):
    from app.models.base import db
    from app.models.lead import Lead
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='Allocation Pending Tenant', slug='alloc-pending-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))
    admin = User(
        name='Admin', email='allocpending-admin@example.invalid',
        password_hash='x', role='superadmin', tenant_id=tenant.id, is_active=True,
    )
    caller = User(
        name='Caller', email='allocpending-caller@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id, is_active=True,
    )
    db.session.add_all([admin, caller])
    db.session.flush()

    truly_unassigned = Lead(
        tenant_id=tenant.id, name='Truly Unassigned', phone='9001110001', status='new',
        is_active=True, created_by=admin.id,
    )
    picked_up_by_caller = Lead(
        tenant_id=tenant.id, name='Picked Up By Caller', phone='9001110002', status='new',
        is_active=True, caller_id=caller.id, created_by=admin.id,
    )
    db.session.add_all([truly_unassigned, picked_up_by_caller])
    db.session.commit()

    token = create_token(str(admin.id), 'superadmin', tenant.id, login_context='tenant')
    headers = {'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms'}
    return tenant, headers


def test_allocation_pending_excludes_leads_with_any_owner_slot():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get('/api/reports/leads', headers=headers)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        health = resp.get_json()['operational_health']
        # Only the lead with zero owners in any slot counts as pending -
        # the one already picked up by a Caller does not, even though its
        # legacy assigned_to field is still empty.
        assert health['allocation_unassigned'] == 1
        assert health['workload_assigned'] == 1
