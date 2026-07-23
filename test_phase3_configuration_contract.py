from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODELS = (ROOT / 'app/models/business_configuration.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'app/services/business_configuration.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'app/routes/configuration.py').read_text(encoding='utf-8')
MIGRATION = (ROOT / 'migrations/phase3_business_configuration_20260723.py').read_text(encoding='utf-8')


def test_status_internal_keys_are_immutable_and_backfilled():
    assert "internal_key not in VALID_STATUSES" in ROUTES
    assert "'internal_key'" not in ROUTES[ROUTES.index("for field in ('display_name'"):ROUTES.index("row.updated_by")]
    for key in ('new','no_answer','follow_up','callback_scheduled','interested',
                'site_visit_planned','site_visit_done','negotiation','booking_done',
                'not_interested','lost','junk'):
        assert f"('{key}'" in MIGRATION


def test_status_display_falls_back_to_existing_contract():
    assert 'STATUS_LABELS[key]' in SERVICE
    assert 'VALID_STATUSES' in SERVICE
    assert "'warm_lead': {'status_in': ['interested', 'site_visit_planned']}" in SERVICE
    assert "'hot_lead': {'status_in': ['site_visit_done', 'negotiation']}" in SERVICE


def test_source_configuration_does_not_change_integration_identity():
    update = ROUTES[ROUTES.index('def update_source'):ROUTES.index("@configuration_bp.get('/business-rules')")]
    for forbidden in ('source_type =', 'webhook_token =', 'credentials ='):
        assert forbidden not in update
    assert "Project.query.filter_by(" in update
    assert "User.query.filter_by(" in update


def test_rule_updates_are_versioned_and_audited():
    assert 'version = (current.version if current else 0) + 1' in ROUTES
    assert 'current.effective_to = datetime.utcnow()' in ROUTES
    assert "module='configuration'" in ROUTES
    assert 'correlation_id=correlation_id' in ROUTES


def test_configuration_is_tenant_scoped_and_permission_protected():
    assert 'tenant_id=_tenant_id()' in ROUTES
    assert "@require_capability('configuration.manage', 'TENANT')" in ROUTES
    assert "@require_capability('configuration.view', 'TENANT')" in ROUTES


def test_migration_is_additive_guarded_and_idempotent():
    upper = MIGRATION.upper()
    assert 'EXPECTED_DATABASE_HOST' in MIGRATION
    assert 'ON CONFLICT DO NOTHING' in upper
    assert '--check' in MIGRATION and '--apply' in MIGRATION
    for forbidden in ('DROP TABLE','TRUNCATE ','DELETE FROM ','UPDATE LEADS','ALTER TABLE LEADS'):
        assert forbidden not in upper
