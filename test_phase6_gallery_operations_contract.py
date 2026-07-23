from pathlib import Path


ROOT = Path(__file__).resolve().parent
ROUTES = (ROOT / 'app/routes/gallery_operations.py').read_text(encoding='utf-8')
VISITS = (ROOT / 'app/models/visit.py').read_text(encoding='utf-8')
EVENTS = (ROOT / 'app/services/notification_events.py').read_text(encoding='utf-8')
MIGRATION = (
    ROOT / 'migrations/phase6_gallery_operations_20260723.py'
).read_text(encoding='utf-8')


def test_gallery_operations_extend_exactly_one_visit_model():
    assert "Visit(" in ROUTES
    assert "__tablename__ = 'visits'" in VISITS
    for forbidden in (
        "class Visitor", "class WalkIn", "class ReceptionQueue",
        "CREATE TABLE reception", "CREATE TABLE visitor", "CREATE TABLE queue",
    ):
        assert forbidden not in ROUTES
        assert forbidden.upper() not in MIGRATION.upper()


def test_reception_dashboard_is_tenant_scoped_date_bounded_and_operational():
    assert "@gallery_operations_bp.get('/dashboard')" in ROUTES
    assert "@require_capability('gallery.view', 'TENANT')" in ROUTES
    assert 'business_date_bounds_utc_naive' in ROUTES
    for metric in (
        'expected_today', 'checked_in', 'waiting', 'in_meeting',
        'completed', 'no_shows', 'walk_ins',
    ):
        assert metric in ROUTES
    assert "'timezone': 'Asia/Kolkata'" in ROUTES


def test_reception_lists_are_bounded_and_driven_by_visit_status():
    assert "@gallery_operations_bp.get('/visits')" in ROUTES
    assert 'per_page = min(100' in ROUTES
    assert 'selectinload(Visit.participants)' in ROUTES
    assert 'joinedload(Visit.location)' in ROUTES
    assert "Visit.status_key.in_(['WAITING', 'CALLED'])" in ROUTES
    assert 'ReceptionQueue.query' not in ROUTES
    for view in (
        'expected', 'arrived', 'waiting', 'inside', 'completed',
        'no_show', 'walk_ins',
    ):
        assert f"'{view}'" in ROUTES


def test_walk_in_creates_checked_in_visit_without_forcing_a_lead():
    block = ROUTES[
        ROUTES.index("def create_walk_in():"):
        ROUTES.index("def _transition(")
    ]
    assert "visit_type_key='WALK_IN'" in block
    assert "status_key='CHECKED_IN'" in block
    assert 'actual_check_in=now' in block
    assert "if not lead and not display_name" in block
    assert "lead_id=lead.id if lead else None" in block
    assert 'Lead(' not in block


def test_waiting_journey_is_explicit_and_transition_guarded():
    for route in (
        "/visits/<int:visit_id>/check-in",
        "/visits/<int:visit_id>/queue-state",
        "/visits/<int:visit_id>/check-out",
        "/visits/<int:visit_id>/no-show",
    ):
        assert route in ROUTES
    for status in ('WAITING', 'CALLED', 'IN_MEETING'):
        assert status in ROUTES
        assert status in MIGRATION
    assert "Visit cannot move from" in ROUTES
    assert "'actual_check_out'" in ROUTES


def test_handoff_reuses_bell_and_notification_event_pipeline_atomically():
    assignment = ROUTES[
        ROUTES.index("def assign_visit("):
        ROUTES.index("@gallery_operations_bp.put('/visits/<int:visit_id>/room')")
    ]
    assert "push_notification(" in ROUTES
    assert 'enqueue_visit_assignment(' in ROUTES
    assert "event_type='visit_assigned'" in EVENTS
    assert 'gallery_visit_assigned' in assignment
    assert 'db.session.commit()' in assignment
    assert assignment.index('_audit(') < assignment.index('_notify_assignment(')
    assert assignment.index('_notify_assignment(') < assignment.index('db.session.commit()')


def test_room_allocation_is_location_safe_without_booking_logic():
    assert "@require_capability('gallery.allocate_room', 'TENANT')" in ROUTES
    assert "room.location_id != row.location_id" in ROUTES
    for forbidden in ('booking conflict', 'calendar', 'reservation overlap'):
        assert forbidden not in ROUTES.lower()


def test_mutations_are_capability_protected_and_correlated():
    for capability in (
        'gallery.check_in', 'gallery.check_out', 'gallery.assign',
        'gallery.allocate_room', 'gallery.archive',
    ):
        assert f"@require_capability('{capability}', 'TENANT')" in ROUTES
        assert capability in MIGRATION
    assert "module='gallery_operations'" in ROUTES
    assert 'correlation_id=correlation_id' in ROUTES
    for action in (
        'gallery_walk_in_created', 'gallery_visit_checked_in',
        'gallery_queue_state_changed', 'gallery_visit_assigned',
        'gallery_room_allocation_changed', 'gallery_visit_checked_out',
    ):
        assert action in ROUTES


def test_references_are_safe_bounded_and_available_to_reception():
    block = ROUTES[
        ROUTES.index("def references():"):
        ROUTES.index("@gallery_operations_bp.get('/dashboard')")
    ]
    assert "@gallery_operations_bp.get('/references')" in ROUTES
    assert "@require_capability('gallery.view', 'TENANT')" in ROUTES
    assert 'tenant_id=_tenant_id()' in block
    assert '.limit(500)' in block
    assert "'email'" not in block
    assert "'phone'" not in block


def test_migration_is_additive_guarded_and_idempotent():
    upper = MIGRATION.upper()
    assert 'EXPECTED_DATABASE_HOST' in MIGRATION
    assert 'ON CONFLICT' in upper
    assert '--check' in MIGRATION and '--apply' in MIGRATION
    for capability in (
        'gallery.view', 'gallery.check_in', 'gallery.check_out',
        'gallery.assign', 'gallery.allocate_room', 'gallery.archive',
        'gallery.configure',
    ):
        assert capability in MIGRATION
    for forbidden in (
        'CREATE TABLE', 'DROP TABLE', 'TRUNCATE ', 'DELETE FROM ',
        'ALTER TABLE LEADS', 'UPDATE LEADS', 'ALTER TABLE VISITS',
    ):
        assert forbidden not in upper


def test_future_self_check_in_uses_existing_visit_foundation():
    for field in ('token_code', 'operational_metadata', 'reception_assigned_user_id'):
        assert field in VISITS
    assert 'qr_code' not in MIGRATION.lower()
    assert 'self_check_in' not in MIGRATION.lower()
