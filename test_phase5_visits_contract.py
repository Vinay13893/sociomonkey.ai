from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODELS = (ROOT / 'app/models/visit.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'app/routes/visits.py').read_text(encoding='utf-8')
MIGRATION = (ROOT / 'migrations/phase5_visits_20260723.py').read_text(encoding='utf-8')
# Visit-payload validation (reference/tenant checks, room/location
# cross-check) lives in visit_builder so pipeline/gallery-operations routes
# can reuse it; visits.py calls it via thin wrappers.
BUILDER = (ROOT / 'app/services/visit_builder.py').read_text(encoding='utf-8')


def test_one_generic_visit_aggregate_supports_required_relationships():
    assert "__tablename__ = 'visits'" in MODELS
    for field in (
        'tenant_id', 'visit_type_key', 'status_key', 'location_id',
        'meeting_room_id', 'project_id', 'lead_id', 'assigned_user_id',
        'created_by', 'updated_by',
    ):
        assert field in MODELS
    assert 'CustomerVisit' not in MODELS
    assert 'GalleryVisit' not in MODELS
    assert 'ChannelPartnerVisit' not in MODELS


def test_visit_participants_are_future_ready_without_premature_foreign_keys():
    assert "__tablename__ = 'visit_participants'" in MODELS
    for participant_type in (
        'LEAD', 'CHANNEL_PARTNER', 'CUSTOMER', 'USER', 'ORGANISATION', 'OTHER',
    ):
        assert participant_type in ROUTES
        assert participant_type in MIGRATION
    participant_model = MODELS[MODELS.index('class VisitParticipant'):MODELS.index('class VisitTag')]
    assert "db.ForeignKey('channel_partners.id')" not in participant_model
    assert 'reference_id' in participant_model
    assert 'participant_metadata' in participant_model


def test_visit_type_and_lifecycle_are_tenant_configurable_with_immutable_keys():
    assert "__tablename__ = 'visit_type_configurations'" in MODELS
    assert "__tablename__ = 'visit_status_configurations'" in MODELS
    for key in (
        'SCHEDULED', 'CHECKED_IN', 'IN_PROGRESS', 'COMPLETED',
        'CANCELLED', 'NO_SHOW',
    ):
        assert key in MIGRATION
    update_config = ROUTES[ROUTES.index('def _update_configuration'):ROUTES.index("@visits_bp.put('/configuration/types")]
    assert "setattr(row, field" in update_config
    assert 'internal_key' not in ROUTES[ROUTES.index('CONFIG_FIELDS ='):ROUTES.index('def _tenant_id')]
    assert "@visits_bp.post('/configuration/types')" in ROUTES
    assert "@visits_bp.post('/configuration/statuses')" in ROUTES
    assert "Visit configuration key already exists" in ROUTES
    assert 'allow_inactive_key' in ROUTES


def test_visit_details_cover_timing_reception_and_metadata_foundations():
    for field in (
        'purpose', 'notes', 'expected_arrival', 'actual_check_in',
        'actual_check_out', 'visitor_count', 'source', 'priority',
        'operational_metadata', 'reception_assigned_user_id',
        'escort_user_id', 'token_code',
    ):
        assert field in MODELS
    assert "__tablename__ = 'visit_tags'" in MODELS
    assert "__tablename__ = 'visit_attachments'" in MODELS
    assert 'file_data' not in MODELS


def test_every_reference_is_tenant_validated_and_room_matches_location():
    assert "tenant_id=_tenant_id()" in ROUTES
    assert "room.location_id != location.id" in BUILDER
    assert "tenant_id=tenant_id" in BUILDER
    for model in ('Project', 'User'):
        assert model in BUILDER
    assert 'Lead' in ROUTES
    assert "Participant lead" in ROUTES
    assert "Participant user" in ROUTES


def test_visit_crud_is_bounded_capability_protected_and_audited():
    for route in (
        "@visits_bp.get('')", "@visits_bp.post('')",
        "@visits_bp.get('/<int:visit_id>')", "@visits_bp.put('/<int:visit_id>')",
        "@visits_bp.post('/<int:visit_id>/archive')",
        "@visits_bp.post('/<int:visit_id>/restore')",
    ):
        assert route in ROUTES
    assert 'per_page = min(100' in ROUTES
    assert "@require_capability('visits.view', 'TENANT')" in ROUTES
    assert "@require_capability('visits.manage', 'TENANT')" in ROUTES
    assert "module='visits'" in ROUTES
    assert 'correlation_id=correlation_id' in ROUTES
    for action in (
        'visit_created', 'visit_updated', 'visit_lifecycle_changed',
        'visit_archived', 'visit_restored',
    ):
        assert action in ROUTES


def test_visits_do_not_mutate_legacy_lead_or_pipeline_state():
    for forbidden in (
        'Lead.status =', 'StatusHistory(', 'assigned_to =',
        'pipeline_group =', 'UPDATE leads', 'ALTER TABLE leads',
    ):
        assert forbidden not in ROUTES
        assert forbidden.upper() not in MIGRATION.upper()


def test_migration_is_additive_guarded_and_idempotent():
    upper = MIGRATION.upper()
    assert 'EXPECTED_DATABASE_HOST' in MIGRATION
    assert 'ON CONFLICT' in upper
    assert 'CREATE TABLE IF NOT EXISTS' in upper
    assert '--check' in MIGRATION and '--apply' in MIGRATION
    for forbidden in (
        'DROP TABLE', 'TRUNCATE ', 'DELETE FROM ', 'UPDATE LEADS',
        'ALTER TABLE LEADS', 'ALTER TABLE PROJECTS',
    ):
        assert forbidden not in upper
