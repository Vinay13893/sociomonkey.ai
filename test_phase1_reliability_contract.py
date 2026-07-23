from pathlib import Path


ROOT = Path(__file__).resolve().parent
INGESTION_ROUTE = (ROOT / 'app/routes/ingestion.py').read_text(encoding='utf-8')
INGESTION_ENGINE = (ROOT / 'app/services/ingestion_engine.py').read_text(encoding='utf-8')
NOTIFICATION_PROCESSOR = (ROOT / 'app/services/notification_processor.py').read_text(encoding='utf-8')
REMINDERS = (ROOT / 'app/services/reminder_scheduler.py').read_text(encoding='utf-8')
PUSH_ROUTES = (ROOT / 'app/routes/push.py').read_text(encoding='utf-8')
SOURCE_ROUTES = (ROOT / 'app/routes/lead_sources.py').read_text(encoding='utf-8')
MIGRATION = (ROOT / 'migrations/phase1_reliability_20260722.py').read_text(encoding='utf-8')


def test_meta_webhook_fails_closed_and_captures_before_enrichment():
    assert 'META_WEBHOOK_REQUIRE_SIGNATURE' in INGESTION_ROUTE
    assert "current_app.config.get('META_APP_SECRET')" in INGESTION_ROUTE
    capture = INGESTION_ROUTE.index('capture_ingestion_event(')
    enrich = INGESTION_ROUTE.index('_meta_enrich_leadgen_entry(', capture)
    assert capture < enrich


def test_realtime_meta_path_does_not_fetch_reporting_insights():
    start = INGESTION_ROUTE.index('def _meta_enrich_leadgen_entry')
    end = INGESTION_ROUTE.index('\ndef ', start + 5)
    body = INGESTION_ROUTE[start:end]
    assert '_meta_fetch_ad_insights_any(' not in body
    assert '_meta_fetch_object_name_any(' not in body


def test_ingestion_and_assignment_event_commit_atomically():
    dispatch = INGESTION_ENGINE.index('dispatch_notification(lead, assignee, log)')
    commit = INGESTION_ENGINE.index('db.session.commit()', dispatch)
    assert dispatch < commit
    assert "idempotency_key=f'ingestion:{log.id}:lead-assigned:{assignee.id}'" in INGESTION_ENGINE


def test_notification_claim_is_conditional_and_recoverable():
    assert "NotificationEvent.status == 'queued'" in NOTIFICATION_PROCESSOR
    assert "'claimed_at': now" in NOTIFICATION_PROCESSOR
    assert 'if claimed == 1:' in NOTIFICATION_PROCESSOR
    assert "event.status != 'sending'" in NOTIFICATION_PROCESSOR
    assert 'dead_lettered_at' in NOTIFICATION_PROCESSOR


def test_reminder_delivery_failure_is_not_marked_successful():
    assert "idempotency_key=f'callback:{callback.id}:{event_kind}:user:{uid}'" in REMINDERS
    rollback = REMINDERS.index('_db.session.rollback()')
    assert 'raise' in REMINDERS[rollback:rollback + 250]


def test_admin_diagnostics_and_retry_routes_are_tenant_scoped():
    assert "@push_bp.route('/diagnostics', methods=['GET'])" in PUSH_ROUTES
    assert "@push_bp.route('/events/<int:event_id>/retry', methods=['POST'])" in PUSH_ROUTES
    assert 'NotificationEvent.tenant_id == user.tenant_id' in PUSH_ROUTES
    assert "@lead_sources_bp.route('/logs/diagnostics', methods=['GET'])" in SOURCE_ROUTES
    assert 'IngestedLeadLog.tenant_id == user.tenant_id' in SOURCE_ROUTES


def test_migration_is_additive_guarded_and_has_no_destructive_sql():
    upper = MIGRATION.upper()
    assert 'ALLOW_PRODUCTION_DB_OPERATION' in MIGRATION
    assert 'EXPECTED_DATABASE_HOST' in MIGRATION
    assert '--check' in MIGRATION and '--apply' in MIGRATION
    for forbidden in ('DROP TABLE', 'TRUNCATE ', 'DELETE FROM', 'UPDATE '):
        assert forbidden not in upper
    assert 'CREATE UNIQUE INDEX IF NOT EXISTS' in upper
