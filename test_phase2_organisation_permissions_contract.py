from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODELS = (ROOT / 'app/models/organisation.py').read_text(encoding='utf-8')
PERMISSIONS = (ROOT / 'app/services/permissions.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'app/routes/organisation.py').read_text(encoding='utf-8')
MIGRATION = (ROOT / 'migrations/phase2_organisation_permissions_20260723.py').read_text(encoding='utf-8')


def test_phase2_models_are_additive_and_tenant_scoped():
    for table in (
        'organisation_units', 'organisation_unit_memberships', 'business_roles',
        'user_business_roles', 'reporting_relationships', 'permission_definitions',
        'role_permissions', 'user_permission_overrides',
    ):
        assert f"__tablename__ = '{table}'" in MODELS
        assert f'CREATE TABLE IF NOT EXISTS {table}' in MIGRATION
    assert 'tenant_id' in MODELS
    assert 'ck_reporting_relationship_not_self' in MODELS


def test_permission_precedence_and_resource_scope_are_fail_closed():
    deny = PERMISSIONS.index("if any(row.effect == 'DENY' for row in matching_overrides)")
    allow = PERMISSIONS.index("if any(row.effect == 'ALLOW' for row in matching_overrides)")
    assert deny < allow
    assert 'requested_ref is not None and str(grant_ref) == str(requested_ref)' in PERMISSIONS
    assert 'UserPermissionOverride.tenant_id == tenant_id' in PERMISSIONS
    assert 'UserBusinessRole.tenant_id == tenant_id' in PERMISSIONS


def test_legacy_users_are_not_guessed_into_new_business_roles():
    assert "ELSE 'LEGACY_TEAM_MEMBER' END" in MIGRATION
    assert "'CALLER':'Caller'" in MIGRATION
    assert "'RELATIONSHIP_MANAGER':'Relationship Manager'" in MIGRATION


def test_admin_routes_require_capabilities_and_preserve_auditability():
    assert "@organisation_bp.route('/units', methods=['POST'])" in ROUTES
    assert "@organisation_bp.route('/reporting-relationships', methods=['POST'])" in ROUTES
    assert "@organisation_bp.route('/users/<int:user_id>/roles', methods=['POST'])" in ROUTES
    assert "@require_capability('permissions.manage', 'TENANT')" in ROUTES
    assert "db.session.add(ActivityLog(" in ROUTES


def test_migration_is_guarded_idempotent_and_non_destructive():
    upper = MIGRATION.upper()
    assert 'EXPECTED_DATABASE_HOST' in MIGRATION
    assert 'ALLOW_PRODUCTION_DB_OPERATION' in (
        ROOT / 'db_safety.py'
    ).read_text(encoding='utf-8')
    assert '--check' in MIGRATION and '--apply' in MIGRATION
    assert 'ON CONFLICT DO NOTHING' in upper
    for forbidden in ('DROP TABLE', 'TRUNCATE ', 'DELETE FROM ', 'ALTER TABLE '):
        assert forbidden not in upper
