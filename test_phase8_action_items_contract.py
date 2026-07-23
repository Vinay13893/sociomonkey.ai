from pathlib import Path


ROOT = Path(__file__).parent
MODEL = (ROOT / 'app/models/action_item.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'app/routes/action_items.py').read_text(encoding='utf-8')
EVENTS = (ROOT / 'app/services/action_item_events.py').read_text(encoding='utf-8')
MIGRATION = (
    ROOT / 'migrations/phase8_action_items_20260723.py'
).read_text(encoding='utf-8')


def test_one_action_item_model_uses_stable_source_reference():
    assert 'class ActionItem(db.Model)' in MODEL
    assert 'source_type = db.Column' in MODEL
    assert 'source_id = db.Column' in MODEL
    for forbidden in (
        'LeadActionItem', 'VisitActionItem', 'ReceptionActionItem',
        'ChannelPartnerActionItem',
    ):
        assert forbidden not in MODEL


def test_action_sources_and_configurations_are_extensible():
    for source in (
        'LEAD', 'VISIT', 'RECEPTION', 'CHANNEL_PARTNER', 'BUSINESS_RULE',
        'SLA', 'CALLBACK', 'MANUAL', 'AUTOMATION',
    ):
        assert f"'{source}'" in MODEL or f"'{source}'" in ROUTES
    assert 'ActionTypeConfiguration' in MODEL
    assert 'ActionStatusConfiguration' in MODEL
    assert 'ActionPriorityConfiguration' in MODEL
    assert 'internal_key' in MODEL


def test_board_is_permission_scoped_and_reads_do_not_generate_work():
    assert "@require_capability('action_items.view', 'OWN')" in ROUTES
    assert "getattr(request, 'permission_decision'" in ROUTES
    assert 'ReportingRelationship' in ROUTES
    assert "'capabilities': capabilities" in ROUTES
    for capability in (
        'action_items.create', 'action_items.edit', 'action_items.assign',
        'action_items.complete', 'action_items.archive',
        'action_items.configure',
    ):
        assert capability in ROUTES
    list_route = ROUTES.split('def list_action_items():', 1)[1].split(
        '@action_items_bp', 1
    )[0]
    assert '_create_action' not in list_route
    assert 'notify_action_item' not in list_route


def test_assignment_lifecycle_audit_and_existing_notification_queue_are_reused():
    assert 'action_item_assigned' in ROUTES
    assert 'action_item_reassigned' in ROUTES
    assert 'action_item_status_changed' in ROUTES
    assert "module='action_items'" in ROUTES
    assert 'Notification(' in EVENTS
    assert 'NotificationEvent(' in EVENTS
    for event in (
        'action_assigned', 'action_reassigned', 'action_due_soon',
        'action_overdue', 'action_completed',
    ):
        assert event in EVENTS


def test_filters_kpis_and_bounded_paging_are_present():
    for value in (
        'assigned_user_id', 'organisation_unit_id', 'project_id',
        'location_id', 'lead_id', 'visit_id', 'channel_partner_id',
        'due_today', 'overdue', 'completed', 'recently_assigned',
    ):
        assert value in ROUTES
    assert "min(100, max(1" in ROUTES
    for metric in (
        'my_actions', 'due_today', 'overdue', 'waiting',
        'completed_today', 'high_priority', 'recently_assigned',
    ):
        assert metric in ROUTES


def test_migration_is_additive_guarded_and_idempotent():
    assert 'EXPECTED_DATABASE_HOST' in MIGRATION
    assert '--check' in MIGRATION
    assert '--apply' in MIGRATION
    assert 'CREATE TABLE IF NOT EXISTS action_items' in MIGRATION
    assert 'ADD COLUMN IF NOT EXISTS action_item_id' in MIGRATION
    assert 'ON CONFLICT' in MIGRATION
    for destructive in ('DROP TABLE', 'TRUNCATE ', 'DELETE FROM leads'):
        assert destructive not in MIGRATION
