"""Integration checks for the Reception walk-in stabilization pass:
Project active-filter, unregistered Channel Partner walk-ins, atomic
new-Lead-from-walk-in creation with duplicate-phone protection, and
assignment defaulting to the Lead's current owner.
"""


def _bootstrap(app):
    from app.models.base import db
    from app.models.location import Location, MeetingRoom
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.visit import VisitStatusConfiguration, VisitTypeConfiguration
    from app.utils.jwt import create_token

    db.create_all()
    tenant = Tenant(name='Reception Stabilization Tenant', slug='reception-stab')
    db.session.add(tenant)
    db.session.flush()
    receptionist = User(
        name='Reception Test', email='reception-stab@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id,
        is_active=True,
    )
    owner = User(
        name='Lead Owner', email='owner-stab@example.invalid',
        password_hash='x', role='team_member', tenant_id=tenant.id,
        is_active=True,
    )
    db.session.add_all([receptionist, owner])
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(
        tenant_id=tenant.id, product_id=product.id, status='active'
    ))
    location = Location(
        tenant_id=tenant.id, code='STAB', name='Stabilization Gallery',
        location_type='SALES_GALLERY', created_by=receptionist.id,
        updated_by=receptionist.id,
    )
    db.session.add(location)
    db.session.flush()
    db.session.add(VisitTypeConfiguration(
        tenant_id=tenant.id, internal_key='WALK_IN',
        display_name='Walk-in', display_order=1, updated_by=receptionist.id,
    ))
    for order, key in enumerate(['SCHEDULED', 'CHECKED_IN'], 1):
        db.session.add(VisitStatusConfiguration(
            tenant_id=tenant.id, internal_key=key,
            display_name=key.title(), display_order=order,
            updated_by=receptionist.id,
        ))
    db.session.commit()
    token = create_token(
        str(receptionist.id), 'team_member', tenant.id, login_context='tenant'
    )
    headers = {
        'Authorization': f'Bearer {token}',
        'X-Product-Slug': 'lms',
        'Content-Type': 'application/json',
    }
    return tenant, receptionist, owner, location, headers


def test_project_reference_list_excludes_inactive():
    from app import create_app
    from app.models.base import db
    from app.models.project import Project
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        db.session.add_all([
            Project(tenant_id=tenant.id, name='Active Project', is_active=True,
                    created_by=receptionist.id),
            Project(tenant_id=tenant.id, name='Archived Project', is_active=False,
                    created_by=receptionist.id),
        ])
        db.session.commit()

        client = app.test_client()
        refs = client.get('/api/gallery-operations/references', headers=headers)
        assert refs.status_code == 200
        names = {row['name'] for row in refs.get_json()['projects']}
        assert names == {'Active Project'}


def test_unregistered_channel_partner_walk_in_uses_free_text():
    from app import create_app
    from app.models.base import db
    from app.models.visit import VisitParticipant
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        client = app.test_client()

        created = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id,
                'participant': {
                    'type': 'CHANNEL_PARTNER',
                    'display_name': 'Unregistered Realty Partners',
                },
                'purpose': 'Unregistered CP walk-in',
            },
        )
        assert created.status_code == 201, created.get_data(as_text=True)
        visit_id = created.get_json()['visit']['id']
        participant = VisitParticipant.query.filter_by(
            tenant_id=tenant.id
        ).filter(VisitParticipant.visit_id == visit_id).first()
        assert participant.participant_type == 'CHANNEL_PARTNER'
        assert participant.reference_id is None
        assert participant.display_name == 'Unregistered Realty Partners'
        assert participant.participant_metadata.get('unregistered') is True

        # Still requires a name when no registered partner is referenced.
        missing_name = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id,
                'participant': {'type': 'CHANNEL_PARTNER'},
                'purpose': 'Should fail',
            },
        )
        assert missing_name.status_code == 400


def test_walk_in_creates_new_lead_atomically_and_defaults_assignment():
    from app import create_app
    from app.models.activity import ActivityLog
    from app.models.base import db
    from app.models.lead import Lead
    from app.models.visit import Visit
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        client = app.test_client()

        created = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id,
                'new_lead': {
                    'name': 'Walk-in Customer', 'phone': '9990001111',
                },
                'purpose': 'New customer walk-in',
            },
        )
        assert created.status_code == 201, created.get_data(as_text=True)
        body = created.get_json()
        assert body['lead']['name'] == 'Walk-in Customer'
        lead_id = body['lead']['id']
        visit_id = body['visit']['id']

        lead = db.session.get(Lead, lead_id)
        visit = db.session.get(Visit, visit_id)
        assert lead is not None and visit.lead_id == lead.id
        assert visit.status_key == 'CHECKED_IN'
        assert ActivityLog.query.filter_by(
            resource_type='Lead', resource_id=lead.id,
            action='lead_created_from_walk_in',
        ).count() == 1

        # Duplicate phone is rejected, not silently duplicated.
        duplicate = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id,
                'new_lead': {
                    'name': 'Second Attempt', 'phone': '9990001111',
                },
                'purpose': 'Duplicate walk-in',
            },
        )
        assert duplicate.status_code == 409
        assert duplicate.get_json()['error'] == 'duplicate_phone'
        assert duplicate.get_json()['existing_lead']['id'] == lead.id
        assert Lead.query.filter_by(tenant_id=tenant.id).count() == 1

        # Assignment defaults to the Lead's current owner at creation time.
        lead.assigned_to = owner.id
        db.session.commit()
        owned = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': lead.id,
                'purpose': 'Existing owned lead walk-in',
            },
        )
        assert owned.status_code == 201, owned.get_data(as_text=True)
        assert owned.get_json()['visit']['assigned_user_id'] == owner.id


if __name__ == '__main__':
    test_project_reference_list_excludes_inactive()
    test_unregistered_channel_partner_walk_in_uses_free_text()
    test_walk_in_creates_new_lead_atomically_and_defaults_assignment()
    print('Reception walk-in stabilization tests passed')
