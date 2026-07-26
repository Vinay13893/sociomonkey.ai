"""Phase 13p: Channel Partner timeline crashed (500) rendering a Visit
entry with no Location - a direct regression from phase13o making
visits.location_id nullable. app.routes.channel_partners.
channel_partner_timeline built its summary string as
f'{row.status_key} at {row.location.name}' unconditionally.
"""


def _bootstrap(app):
    from app.models.base import db
    from app.models.channel_partner import ChannelPartner
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import Visit, VisitParticipant
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='CP Timeline No Location Tenant', slug='cp-timeline-noloc-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(tenant_id=tenant.id, product_id=product.id, status='active'))

    admin = User(
        name='Admin', email='cptimeline-admin@example.invalid',
        password_hash='x', role='superadmin', tenant_id=tenant.id, is_active=True,
    )
    db.session.add(admin)
    db.session.flush()

    partner = ChannelPartner(
        tenant_id=tenant.id, code='CPNL', partner_type='INDIVIDUAL', name='No Location Partner',
        created_by=admin.id, updated_by=admin.id,
    )
    db.session.add(partner)
    db.session.flush()

    visit = Visit(
        tenant_id=tenant.id, visit_type_key='MEETING', status_key='SCHEDULED',
        location_id=None, purpose='Meeting at the partner office',
        operational_metadata={'venue_note': "At the partner's office"},
        created_by=admin.id, updated_by=admin.id,
    )
    db.session.add(visit)
    db.session.flush()
    db.session.add(VisitParticipant(
        tenant_id=tenant.id, visit_id=visit.id, participant_type='CHANNEL_PARTNER',
        reference_id=partner.id, display_name=partner.name, is_primary=True,
    ))
    db.session.commit()

    token = create_token(str(admin.id), 'superadmin', tenant.id, login_context='tenant')
    headers = {'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms'}
    return tenant, partner, headers


def test_timeline_does_not_crash_on_visit_without_location():
    from app import create_app

    app = create_app('testing')
    with app.app_context():
        tenant, partner, headers = _bootstrap(app)
        client = app.test_client()

        resp = client.get(f'/api/channel-partners/{partner.id}/timeline', headers=headers)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        entries = resp.get_json()['timeline']
        visit_entries = [e for e in entries if e['type'] == 'VISIT']
        assert len(visit_entries) == 1
        assert "At the partner's office" in visit_entries[0]['summary']
