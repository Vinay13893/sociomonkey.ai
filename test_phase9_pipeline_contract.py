from pathlib import Path


ROOT = Path(__file__).parent
MODEL = (ROOT / 'app/models/pipeline.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'app/services/pipeline_engine.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'app/routes/pipeline.py').read_text(encoding='utf-8')
MIGRATION = (
    ROOT / 'migrations/phase9_pipeline_engine_20260724.py'
).read_text(encoding='utf-8')


def test_pipeline_is_orchestration_not_a_second_lead_record():
    assert 'class PipelineTransition(db.Model)' in MODEL
    assert "lead_id = db.Column" in MODEL
    assert 'name = db.Column' not in MODEL
    assert 'phone = db.Column' not in MODEL
    assert 'from_stage_key' in MODEL
    assert 'to_stage_key' in MODEL


def test_transitions_are_append_only_and_audited():
    assert 'transition_lead' in SERVICE
    assert 'PipelineTransition(' in SERVICE
    assert 'StatusHistory(' in SERVICE
    assert 'ActivityLog(' in SERVICE
    assert 'correlation_id' in SERVICE
    assert '.delete(' not in SERVICE
    assert '.update(' not in SERVICE


def test_rules_actions_visits_notifications_and_cp_reuse_existing_foundations():
    assert 'evaluate_rules' in SERVICE
    assert 'ActionItem(' in SERVICE
    assert 'NotificationEvent(' in SERVICE
    assert 'visit_id' in MODEL
    assert 'channel_partner_id' in MODEL
    assert 'manager_override' in MODEL
    assert 'required_action_type_keys' in SERVICE


def test_pipeline_reads_are_bounded_and_capability_scoped():
    assert "@require_capability('pipeline.view', 'OWN')" in ROUTES
    assert "@require_capability('pipeline.move', 'OWN')" in ROUTES
    assert "@require_capability('pipeline.assign', 'TEAM')" in ROUTES
    assert 'min(50, max(1' in ROUTES
    assert ".limit(500)" in ROUTES
    for endpoint in (
        "'/stages'", "'/dashboard'",
        "'/stages/<string:stage_key>/leads'",
        "'/leads/<int:lead_id>/history'",
    ):
        assert endpoint in ROUTES


def test_migration_is_additive_guarded_and_idempotent():
    assert 'EXPECTED_DATABASE_HOST' in MIGRATION
    assert 'get_database_url(require_production_confirmation=False)' in MIGRATION
    assert '--check' in MIGRATION
    assert '--apply' in MIGRATION
    assert 'CREATE TABLE IF NOT EXISTS pipeline_transitions' in MIGRATION
    assert 'pipeline_transitions_immutable' in MIGRATION
    assert 'BEFORE UPDATE OR DELETE ON pipeline_transitions' in MIGRATION
    assert 'ADD COLUMN IF NOT EXISTS' in MIGRATION
    assert 'ON CONFLICT DO NOTHING' in MIGRATION
    for forbidden in (
        'DROP TABLE', 'TRUNCATE ', 'DELETE FROM leads',
        'UPDATE leads SET status',
    ):
        assert forbidden not in MIGRATION
