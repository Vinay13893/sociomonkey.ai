from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _text(path):
    return path.read_text(encoding='utf-8')


def test_phase11_extends_the_existing_queue_only():
    model = _text(ROOT / 'app' / 'models' / 'push.py')
    migration = _text(
        ROOT / 'migrations' / 'phase11_notification_reliability_20260724.py'
    )
    assert 'class NotificationEvent' in model
    assert 'class NotificationDeliveryAttempt' in model
    assert "CREATE TABLE IF NOT EXISTS notification_delivery_attempts" in migration
    assert 'notification_queues' not in migration
    assert 'CREATE QUEUE' not in migration


def test_phase11_migration_is_additive_idempotent_and_guarded():
    source = _text(
        ROOT / 'migrations' / 'phase11_notification_reliability_20260724.py'
    )
    assert 'ADD COLUMN IF NOT EXISTS' in source
    assert 'CREATE TABLE IF NOT EXISTS' in source
    assert 'CREATE INDEX IF NOT EXISTS' in source
    assert 'EXPECTED_DATABASE_HOST' in source
    assert 'DROP TABLE' not in source
    assert 'TRUNCATE' not in source
    assert 'DELETE FROM' not in source
    assert 'UPDATE notification_events' not in source


def test_phase11_attempt_history_is_immutable():
    source = _text(
        ROOT / 'migrations' / 'phase11_notification_reliability_20260724.py'
    )
    assert 'notification_delivery_attempts_immutable' in source
    assert 'BEFORE UPDATE OR DELETE ON notification_delivery_attempts' in source


def test_phase11_worker_is_bounded_and_recoverable():
    source = _text(ROOT / 'app' / 'services' / 'notification_processor.py')
    assert '_MAX_RUN_SECONDS = 45' in source
    assert 'min(int(batch_size or _BATCH_SIZE), 10)' in source
    assert '_BACKOFF_MINUTES' in source
    assert 'Recovered from stale sending state' in source
    assert "'dead_lettered'" in source
    assert '_WORKER_LOCK.acquire(blocking=False)' in source


def test_phase11_operator_routes_are_capability_and_tenant_scoped():
    routes = _text(ROOT / 'app' / 'routes' / 'push.py')
    for path in (
        '/operations/summary',
        '/operations/events',
        '/operations/events/<int:event_id>',
        '/operations/events/<int:event_id>/replay',
        '/operations/events/archive-completed',
    ):
        assert path in routes
    assert "@require_capability('notifications.view', 'TENANT')" in routes
    assert "@require_capability('notifications.retry', 'TENANT')" in routes
    assert "@require_capability('notifications.manage', 'TENANT')" in routes
    assert 'tenant_id=request.current_user.tenant_id' in routes


def test_phase11_has_one_delivery_worker_entrypoint():
    app_source = _text(ROOT / 'app' / '__init__.py')
    cron_source = _text(ROOT / 'app' / 'routes' / 'cron.py')
    assert "'delegated_to': '/api/cron/drain-notifications'" in app_source
    assert 'process_notification_queue' not in app_source[
        app_source.index("'/api/internal/reminders/process'"):
        app_source.index("'/api/internal/jobs/process'")
    ]
    assert 'process_notification_queue' in cron_source


def test_phase11_correlation_spans_core_operational_modules():
    paths = (
        ROOT / 'app' / 'services' / 'ingestion_engine.py',
        ROOT / 'app' / 'services' / 'pipeline_engine.py',
        ROOT / 'app' / 'services' / 'action_item_events.py',
        ROOT / 'app' / 'services' / 'notification_events.py',
        ROOT / 'app' / 'services' / 'channel_partner_events.py',
        ROOT / 'app' / 'routes' / 'reports.py',
    )
    for path in paths:
        assert 'correlation_id' in _text(path), path
