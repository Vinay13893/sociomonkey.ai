from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODELS = (ROOT / 'app/models/location.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'app/routes/locations.py').read_text(encoding='utf-8')
MIGRATION = (ROOT / 'migrations/phase4_locations_rooms_20260723.py').read_text(encoding='utf-8')


def test_location_is_generic_tenant_platform_entity():
    assert "__tablename__ = 'locations'" in MODELS
    for field in ('tenant_id','brand_id','location_type','address_line_1','city',
                  'latitude','longitude','contact_details','working_hours','is_active'):
        assert field in MODELS
    assert 'lead_id' not in MODELS
    assert 'assigned_user' not in MODELS
    assert 'user_location' not in MODELS.lower()


def test_project_location_is_many_to_many_and_tenant_validated():
    assert "__tablename__ = 'project_locations'" in MODELS
    assert "'project_id', 'location_id', 'relationship_type'" in MODELS
    assert 'Project.tenant_id == _tenant_id()' in ROUTES
    assert '_sync_projects' in ROUTES


def test_room_belongs_to_location_without_booking_workflow():
    assert "__tablename__ = 'meeting_rooms'" in MODELS
    assert "db.ForeignKey('locations.id')" in MODELS
    assert "capacity > 0" in MODELS
    for status in ('AVAILABLE','OCCUPIED','RESERVED','MAINTENANCE','OUT_OF_SERVICE'):
        assert status in ROUTES and status in MIGRATION
    for forbidden in ('booking_id','calendar_id','schedule_conflict'):
        assert forbidden not in MODELS


def test_crud_archive_restore_are_capability_protected():
    for route in ("@locations_bp.post('')","@locations_bp.put('/<int:location_id>')",
                  "@locations_bp.post('/<int:location_id>/archive')",
                  "@locations_bp.post('/<int:location_id>/restore')",
                  "@locations_bp.post('/meeting-rooms')",
                  "@locations_bp.put('/meeting-rooms/<int:room_id>')"):
        assert route in ROUTES
    assert "@require_capability('locations.manage', 'TENANT')" in ROUTES
    assert "@require_capability('meeting_rooms.manage', 'TENANT')" in ROUTES


def test_every_mutation_has_correlated_activity_audit():
    assert "module='locations'" in ROUTES
    assert 'correlation_id=cid' in ROUTES
    for action in ('location_created','location_updated','location_archived','location_restored',
                   'meeting_room_created','meeting_room_updated','meeting_room_archived',
                   'meeting_room_restored'):
        assert action in ROUTES


def test_list_queries_are_bounded_and_tenant_scoped():
    assert 'per_page = min(100' in ROUTES
    assert 'tenant_id=_tenant_id()' in ROUTES
    assert '.limit(per_page)' in ROUTES


def test_migration_is_additive_guarded_and_idempotent():
    upper=MIGRATION.upper()
    assert 'EXPECTED_DATABASE_HOST' in MIGRATION
    assert 'ON CONFLICT' in upper
    assert '--check' in MIGRATION and '--apply' in MIGRATION
    for forbidden in ('DROP TABLE','TRUNCATE ','DELETE FROM ','ALTER TABLE LEADS','UPDATE LEADS'):
        assert forbidden not in upper
