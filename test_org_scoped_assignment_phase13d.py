"""Integration checks for Phase 13d: project/org-unit-scoped Calling
Manager auto-assignment (app.services.org_scope, and the new tier in
app.services.ingestion_engine.create_lead). Dark-launched: every check
here explicitly proves the feature is a no-op unless a FeatureFlag row is
created for the tenant, and that project_id/organisation_unit_id being
unset degrades gracefully rather than erroring.
"""


def _bootstrap(app):
    from app.models.base import db
    from app.models.organisation import BusinessRole, OrganisationUnit, UserBusinessRole
    from app.models.product import Product, TenantProduct
    from app.models.project import Project
    from app.models.tenant import Tenant
    from app.models.user import User

    db.create_all()
    tenant = Tenant(name='Org Scoped Assignment Tenant', slug='orgscope-tenant')
    db.session.add(tenant)
    db.session.flush()
    product = Product.query.filter_by(slug='lms').first()
    assert product
    db.session.add(TenantProduct(
        tenant_id=tenant.id, product_id=product.id, status='active'
    ))
    root = OrganisationUnit(
        tenant_id=tenant.id, code='ROOT', name='Org Scoped Assignment Tenant',
        unit_type='TENANT_ROOT',
    )
    project_unit = OrganisationUnit(
        tenant_id=tenant.id, code='NINEZERO', name='Nine Zero Sales Team',
        unit_type='PROJECT',
    )
    db.session.add_all([root, project_unit])
    db.session.flush()
    project = Project(
        tenant_id=tenant.id, name='Nine Zero', organisation_unit_id=project_unit.id,
    )
    unscoped_project = Project(tenant_id=tenant.id, name='Unscoped Project')
    db.session.add_all([project, unscoped_project])
    db.session.flush()

    calling_manager_role = BusinessRole(
        tenant_id=tenant.id, key='CALLING_MANAGER', display_name='Calling Manager',
        is_active=True,
    )
    db.session.add(calling_manager_role)
    db.session.flush()

    project_cm = User(
        name='Project Calling Manager', email='orgscope-pcm@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
    )
    root_cm = User(
        name='Root Calling Manager', email='orgscope-rcm@example.invalid',
        password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
    )
    db.session.add_all([project_cm, root_cm])
    db.session.flush()
    db.session.add(UserBusinessRole(
        tenant_id=tenant.id, user_id=project_cm.id, business_role_id=calling_manager_role.id,
        organisation_unit_id=project_unit.id, is_primary=True,
    ))
    db.session.add(UserBusinessRole(
        tenant_id=tenant.id, user_id=root_cm.id, business_role_id=calling_manager_role.id,
        organisation_unit_id=root.id, is_primary=True,
    ))
    db.session.commit()
    return tenant, root, project_unit, project, unscoped_project, project_cm, root_cm


def test_resolve_pool_for_role_prefers_project_unit_falls_back_to_root():
    from app import create_app
    from app.services.org_scope import resolve_pool_for_role

    app = create_app('testing')
    with app.app_context():
        tenant, root, project_unit, project, unscoped_project, project_cm, root_cm = _bootstrap(app)

        pool, resolved_unit = resolve_pool_for_role(tenant.id, 'CALLING_MANAGER', project_unit.id)
        assert [u.id for u in pool] == [project_cm.id]
        assert resolved_unit == project_unit.id

        # A unit with no CALLING_MANAGER holders of its own falls back to
        # the tenant's root pool instead of returning empty.
        empty_unit_pool, resolved = resolve_pool_for_role(tenant.id, 'CALLING_MANAGER', None)
        assert [u.id for u in empty_unit_pool] == [root_cm.id]
        assert resolved == root.id

        no_role_pool, resolved_none = resolve_pool_for_role(tenant.id, 'RELATIONSHIP_MANAGER', project_unit.id)
        assert no_role_pool == [] and resolved_none is None


def test_resolve_org_scoped_assignee_round_robins_and_persists_state():
    from app import create_app
    from app.models.base import db
    from app.models.organisation import BusinessRole, RoleAssignmentRotation, UserBusinessRole
    from app.models.user import User
    from app.services.org_scope import resolve_org_scoped_assignee

    app = create_app('testing')
    with app.app_context():
        tenant, root, project_unit, project, unscoped_project, project_cm, root_cm = _bootstrap(app)
        second_cm = User(
            name='Second Project CM', email='orgscope-pcm2@example.invalid',
            password_hash='x', role='sales_manager', tenant_id=tenant.id, is_active=True,
        )
        db.session.add(second_cm)
        db.session.flush()
        role = BusinessRole.query.filter_by(tenant_id=tenant.id, key='CALLING_MANAGER').first()
        db.session.add(UserBusinessRole(
            tenant_id=tenant.id, user_id=second_cm.id, business_role_id=role.id,
            organisation_unit_id=project_unit.id, is_primary=True,
        ))
        db.session.commit()

        picks = [
            resolve_org_scoped_assignee(tenant.id, 'CALLING_MANAGER', project_unit.id).id
            for _ in range(4)
        ]
        db.session.commit()
        # Two-person pool, 4 picks -> exactly alternates, proving state
        # actually persists across calls instead of always picking index 0.
        assert picks == [project_cm.id, second_cm.id, project_cm.id, second_cm.id]
        rotation = RoleAssignmentRotation.query.filter_by(
            tenant_id=tenant.id, business_role_key='CALLING_MANAGER',
            organisation_unit_id=project_unit.id,
        ).first()
        assert rotation is not None and rotation.last_index == 0  # wrapped back to 0 after 4 picks of a 2-pool


def test_create_lead_calling_manager_assignment_is_off_by_default():
    from app import create_app
    from app.models.base import db
    from app.models.ingestion import IngestedLeadLog, LeadSource
    from app.services.ingestion_engine import create_lead

    app = create_app('testing')
    with app.app_context():
        tenant, root, project_unit, project, unscoped_project, project_cm, root_cm = _bootstrap(app)
        source = LeadSource(tenant_id=tenant.id, name='Test Source', source_type='webhook')
        db.session.add(source)
        db.session.flush()
        log = IngestedLeadLog(tenant_id=tenant.id, source_id=source.id, source_type='webhook')
        db.session.add(log)
        db.session.flush()

        # No FeatureFlag row exists for this tenant - must be a total no-op,
        # exactly as every tenant behaves today.
        lead = create_lead(
            mapped={'name': 'No Flag Lead', 'phone': '9003330001', 'project_id': project.id},
            source=source, assignee=None, log=log,
        )
        db.session.commit()
        assert lead.calling_manager_id is None


def test_create_lead_calling_manager_assignment_when_enabled():
    from app import create_app
    from app.models.base import db
    from app.models.ingestion import IngestedLeadLog, LeadSource
    from app.models.product import FeatureFlag
    from app.services.ingestion_engine import create_lead

    app = create_app('testing')
    with app.app_context():
        tenant, root, project_unit, project, unscoped_project, project_cm, root_cm = _bootstrap(app)
        db.session.add(FeatureFlag(
            tenant_id=tenant.id, flag_key='org_scoped_calling_manager_assignment',
            is_enabled=True,
        ))
        source = LeadSource(tenant_id=tenant.id, name='Test Source', source_type='webhook')
        db.session.add(source)
        db.session.flush()
        log = IngestedLeadLog(tenant_id=tenant.id, source_id=source.id, source_type='webhook')
        db.session.add(log)
        db.session.commit()

        lead = create_lead(
            mapped={'name': 'Flagged Lead', 'phone': '9003330002', 'project_id': project.id},
            source=source, assignee=None, log=log,
        )
        db.session.commit()
        assert lead.calling_manager_id == project_cm.id
        # The existing legacy assignee resolution is completely untouched -
        # no `assignee` was passed, so both legacy fields stay empty.
        assert lead.assigned_to is None and lead.sales_manager_id is None

        # A project with no organisation_unit_id at all falls back to the
        # tenant's root Calling Manager pool rather than staying empty.
        unscoped_lead = create_lead(
            mapped={'name': 'Unscoped Project Lead', 'phone': '9003330003', 'project_id': unscoped_project.id},
            source=source, assignee=None, log=log,
        )
        db.session.commit()
        assert unscoped_lead.calling_manager_id == root_cm.id

        # No project_id at all (e.g. a form with no project mapping) -
        # nothing to scope by, must stay empty rather than guessing.
        no_project_lead = create_lead(
            mapped={'name': 'No Project Lead', 'phone': '9003330004'},
            source=source, assignee=None, log=log,
        )
        db.session.commit()
        assert no_project_lead.calling_manager_id is None


def test_project_api_round_trips_organisation_unit_id():
    from app import create_app
    from app.models.base import db
    from app.models.organisation import OrganisationUnit
    from app.models.product import Product, TenantProduct
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.utils.jwt import create_token

    app = create_app('testing')
    with app.app_context():
        db.create_all()
        tenant = Tenant(name='Project API Tenant', slug='project-api-tenant')
        db.session.add(tenant)
        db.session.flush()
        product = Product.query.filter_by(slug='lms').first()
        assert product
        db.session.add(TenantProduct(
            tenant_id=tenant.id, product_id=product.id, status='active'
        ))
        admin = User(
            name='Admin', email='project-api-admin@example.invalid',
            password_hash='x', role='superadmin', tenant_id=tenant.id, is_active=True,
        )
        unit = OrganisationUnit(
            tenant_id=tenant.id, code='UNIT1', name='Unit One', unit_type='PROJECT',
        )
        db.session.add_all([admin, unit])
        db.session.commit()
        token = create_token(str(admin.id), 'superadmin', tenant.id, login_context='tenant')
        headers = {
            'Authorization': f'Bearer {token}', 'X-Product-Slug': 'lms',
            'Content-Type': 'application/json',
        }
        client = app.test_client()

        created = client.post(
            '/api/projects', headers=headers,
            json={'name': 'Scoped Project', 'organisation_unit_id': unit.id},
        )
        assert created.status_code == 201, created.get_data(as_text=True)
        project_id = created.get_json()['project']['id']
        assert created.get_json()['project']['organisation_unit_id'] == unit.id

        updated = client.put(
            f'/api/projects/{project_id}', headers=headers,
            json={'organisation_unit_id': None},
        )
        assert updated.status_code == 200, updated.get_data(as_text=True)
        assert updated.get_json()['project']['organisation_unit_id'] is None
