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
    for order, key in enumerate(['SCHEDULED', 'CHECKED_IN', 'COMPLETED'], 1):
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


def test_new_lead_walk_in_defaults_source_to_walk_in():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead
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
                'new_lead': {'name': 'No Source Given', 'phone': '9990002222'},
                'purpose': 'Walk-in',
            },
        )
        assert created.status_code == 201, created.get_data(as_text=True)
        lead = db.session.get(Lead, created.get_json()['lead']['id'])
        assert lead.source == 'Walk-in'


def test_assign_visit_syncs_lead_owner_only_when_unset():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        client = app.test_client()
        other = _add_user(tenant, 'Other RM', 'other-rm-stab@example.invalid')

        # Unowned lead: assigning the Visit also sets the Lead's owner.
        unowned = Lead(
            tenant_id=tenant.id, name='Unowned Lead', phone='9990003333',
            status='new', created_by=receptionist.id, is_active=True,
        )
        db.session.add(unowned)
        db.session.commit()
        created = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': unowned.id,
                'purpose': 'Walk-in',
            },
        )
        assert created.status_code == 201, created.get_data(as_text=True)
        visit_id = created.get_json()['visit']['id']
        resp = client.put(
            f'/api/gallery-operations/visits/{visit_id}/assignment',
            headers=headers, json={'assigned_user_id': owner.id},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        db.session.refresh(unowned)
        assert unowned.assigned_to == owner.id

        # Already-owned lead: reassigning the Visit does NOT overwrite the
        # Lead's existing owner.
        owned = Lead(
            tenant_id=tenant.id, name='Owned Lead', phone='9990004444',
            status='new', assigned_to=owner.id,
            created_by=receptionist.id, is_active=True,
        )
        db.session.add(owned)
        db.session.commit()
        created2 = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': owned.id,
                'purpose': 'Walk-in',
            },
        )
        visit_id2 = created2.get_json()['visit']['id']
        resp2 = client.put(
            f'/api/gallery-operations/visits/{visit_id2}/assignment',
            headers=headers, json={'assigned_user_id': other.id},
        )
        assert resp2.status_code == 200, resp2.get_data(as_text=True)
        db.session.refresh(owned)
        assert owned.assigned_to == owner.id  # unchanged


def _add_user(tenant, name, email):
    from app.models.base import db
    from app.models.user import User
    user = User(
        name=name, email=email, password_hash='x', role='team_member',
        tenant_id=tenant.id, is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_checkout_advances_lead_to_site_visit_done_without_failing_on_error():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        client = app.test_client()

        lead = Lead(
            tenant_id=tenant.id, name='Checkout Lead', phone='9990005555',
            status='new', created_by=receptionist.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()
        created = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': lead.id,
                'purpose': 'Walk-in',
            },
        )
        visit_id = created.get_json()['visit']['id']
        resp = client.post(
            f'/api/gallery-operations/visits/{visit_id}/check-out', headers=headers,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        db.session.refresh(lead)
        assert lead.status == 'site_visit_done'

        # Checking out a second, unrelated walk-in for the SAME lead (already
        # past site_visit_done) must still succeed - the pipeline nudge is
        # best-effort and never blocks the physical checkout action.
        created2 = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': lead.id,
                'purpose': 'Second walk-in',
            },
        )
        visit_id2 = created2.get_json()['visit']['id']
        resp2 = client.post(
            f'/api/gallery-operations/visits/{visit_id2}/check-out', headers=headers,
        )
        assert resp2.status_code == 200, resp2.get_data(as_text=True)


def test_lead_lookup_finds_leads_hidden_from_the_countable_leads_endpoint():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        client = app.test_client()

        # A manually-created lead with no trustworthy-provenance evidence -
        # exactly the kind of row apply_valid_lead_capture_scope (used by
        # GET /api/leads) can exclude, but that genuinely exists and must
        # still be findable for walk-in linking/duplicate-detection purposes.
        lead = Lead(
            tenant_id=tenant.id, name='Findable Lead', phone='9990006666',
            status='new', source='Manual', created_by=receptionist.id,
            is_active=True,
        )
        db.session.add(lead)
        db.session.commit()

        resp = client.get(
            '/api/gallery-operations/lead-lookup?search=9990006666', headers=headers,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        results = resp.get_json()['leads']
        assert len(results) == 1
        assert results[0]['id'] == lead.id
        # Phone is masked, not returned in full.
        assert results[0]['phone_masked'] != lead.phone
        assert results[0]['phone_masked'].endswith(lead.phone[-4:])
        assert '*' in results[0]['phone_masked']


def test_reception_search_finds_visits_outside_current_tab_and_date():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        client = app.test_client()

        lead = Lead(
            tenant_id=tenant.id, name='Findable Visitor', phone='9990007777',
            status='new', created_by=receptionist.id, is_active=True,
        )
        db.session.add(lead)
        db.session.commit()
        created = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': lead.id,
                'purpose': 'Walk-in',
            },
        )
        visit_id = created.get_json()['visit']['id']
        client.post(
            f'/api/gallery-operations/visits/{visit_id}/check-out', headers=headers,
        )

        # The default view ('expected', today) would never include a visit
        # that already completed - search must find it anyway.
        resp = client.get(
            '/api/gallery-operations/visits?view=expected&search=Findable+Visitor',
            headers=headers,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        ids = [v['id'] for v in resp.get_json()['visits']]
        assert visit_id in ids


def test_soft_deleted_lead_does_not_block_walkin_duplicate_phone_check():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        client = app.test_client()

        # A previously-deleted lead with this phone must not permanently
        # block re-registering the same number - it's invisible to
        # lead-lookup already (is_active=False), so a duplicate-phone 409
        # against it is a dead end the user has no way to resolve.
        deleted = Lead(
            tenant_id=tenant.id, name='Deleted Lead', phone='9990008888',
            status='new', created_by=receptionist.id, is_active=False,
        )
        db.session.add(deleted)
        db.session.commit()

        lookup = client.get(
            '/api/gallery-operations/lead-lookup?search=9990008888', headers=headers,
        )
        assert lookup.get_json()['leads'] == []

        created = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id,
                'new_lead': {'name': 'Reused Number', 'phone': '9990008888'},
                'purpose': 'Walk-in',
            },
        )
        assert created.status_code == 201, created.get_data(as_text=True)
        assert created.get_json()['lead']['name'] == 'Reused Number'


def test_assign_visit_routes_manager_role_to_sales_manager_field():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead
    from app.models.user import User
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        client = app.test_client()
        manager = User(
            name='Reception Manager', email='reception-mgr-stab@example.invalid',
            password_hash='x', role='sales_manager', tenant_id=tenant.id,
            is_active=True,
        )
        db.session.add(manager)
        db.session.commit()

        # Assigning a Sales Manager from Reception must route into
        # lead.sales_manager_id (the routing/hierarchy field), never into
        # lead.assigned_to (the RM actually working the lead) - picking a
        # manager for triage/calling must not masquerade as assigning the RM.
        unowned = Lead(
            tenant_id=tenant.id, name='Needs Manager', phone='9990009999',
            status='new', created_by=receptionist.id, is_active=True,
        )
        db.session.add(unowned)
        db.session.commit()
        created = client.post(
            '/api/gallery-operations/walk-ins', headers=headers,
            json={
                'location_id': location.id, 'lead_id': unowned.id,
                'purpose': 'Walk-in',
            },
        )
        visit_id = created.get_json()['visit']['id']
        resp = client.put(
            f'/api/gallery-operations/visits/{visit_id}/assignment',
            headers=headers, json={'assigned_user_id': manager.id},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        db.session.refresh(unowned)
        assert unowned.sales_manager_id == manager.id
        assert unowned.assigned_to is None

        # A team_member assigned afterward still fills assigned_to (the two
        # fields are independent) - the RM slot isn't blocked by the
        # manager routing having already happened.
        resp2 = client.put(
            f'/api/gallery-operations/visits/{visit_id}/assignment',
            headers=headers, json={'assigned_user_id': owner.id},
        )
        assert resp2.status_code == 200, resp2.get_data(as_text=True)
        db.session.refresh(unowned)
        assert unowned.assigned_to == owner.id
        assert unowned.sales_manager_id == manager.id  # untouched


def test_lead_lookup_includes_project_and_channel_partner_ids():
    from app import create_app
    from app.models.base import db
    from app.models.lead import Lead
    from app.models.project import Project
    import app.services.permissions as permissions

    app = create_app('testing')
    permissions.capability_decision = lambda user, capability, scope='OWN', scope_ref_id=None: {
        'allowed': True, 'source': 'test', 'scope': scope,
    }
    with app.app_context():
        tenant, receptionist, owner, location, headers = _bootstrap(app)
        client = app.test_client()
        project = Project(
            tenant_id=tenant.id, name='Lookup Project', is_active=True,
            created_by=receptionist.id,
        )
        db.session.add(project)
        db.session.flush()

        # The walk-in dialog's "Find existing lead" pick needs project_id
        # (not just project_name) to pre-select the Project dropdown -
        # a name-only response can't drive a <select>.
        lead = Lead(
            tenant_id=tenant.id, name='Autofill Lead', phone='9990001010',
            status='new', created_by=receptionist.id, is_active=True,
            project_id=project.id,
        )
        db.session.add(lead)
        db.session.commit()

        resp = client.get(
            '/api/gallery-operations/lead-lookup?search=Autofill', headers=headers,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        result = resp.get_json()['leads'][0]
        assert result['project_id'] == project.id
        assert result['project_name'] == 'Lookup Project'
        assert 'channel_partner_id' in result


if __name__ == '__main__':
    test_project_reference_list_excludes_inactive()
    test_unregistered_channel_partner_walk_in_uses_free_text()
    test_walk_in_creates_new_lead_atomically_and_defaults_assignment()
    test_new_lead_walk_in_defaults_source_to_walk_in()
    test_assign_visit_syncs_lead_owner_only_when_unset()
    test_checkout_advances_lead_to_site_visit_done_without_failing_on_error()
    test_lead_lookup_finds_leads_hidden_from_the_countable_leads_endpoint()
    test_reception_search_finds_visits_outside_current_tab_and_date()
    test_soft_deleted_lead_does_not_block_walkin_duplicate_phone_check()
    test_assign_visit_routes_manager_role_to_sales_manager_field()
    test_lead_lookup_includes_project_and_channel_partner_ids()
    print('Reception walk-in stabilization tests passed')
