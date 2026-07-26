"""Phase 13i: Operational Board gained a due-date range filter
(date_from/date_to against ActionItem.due_at), matching the pattern
already used for Reception's business-date range."""


def _bootstrap(app):
    from app.models.action_item import ActionItem
    from app.models.base import db
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.utils.jwt import create_token
    from datetime import datetime

    db.create_all()
    tenant = Tenant(name='AI Due Range Tenant', slug='ai-due-range-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))
    admin = User(
        name='Admin', email='aidue-admin@example.invalid',
        password_hash='x', role='superadmin', tenant_id=tenant.id, is_active=True,
    )
    db.session.add(admin)
    db.session.flush()

    early = ActionItem(
        tenant_id=tenant.id, title='Early Action', source_type='MANUAL',
        action_type_key='MANUAL', status_key='OPEN', priority_key='NORMAL', assigned_user_id=admin.id,
        due_at=datetime(2026, 1, 5), created_by=admin.id, updated_by=admin.id,
    )
    in_range = ActionItem(
        tenant_id=tenant.id, title='In Range Action', source_type='MANUAL',
        action_type_key='MANUAL', status_key='OPEN', priority_key='NORMAL', assigned_user_id=admin.id,
        due_at=datetime(2026, 7, 22), created_by=admin.id, updated_by=admin.id,
    )
    late = ActionItem(
        tenant_id=tenant.id, title='Late Action', source_type='MANUAL',
        action_type_key='MANUAL', status_key='OPEN', priority_key='NORMAL', assigned_user_id=admin.id,
        due_at=datetime(2026, 12, 1), created_by=admin.id, updated_by=admin.id,
    )
    db.session.add_all([early, in_range, late])
    db.session.commit()

    token = create_token(str(admin.id), 'superadmin', tenant.id, login_context='tenant')
    headers = {'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms'}
    return tenant, headers


def test_action_items_filters_by_due_date_range():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get(
            '/api/action-items?date_from=2026-07-20&date_to=2026-07-25',
            headers=headers,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        titles = {row['title'] for row in resp.get_json()['action_items']}
        assert titles == {'In Range Action'}
