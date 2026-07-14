from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP_INIT = (ROOT / 'app' / '__init__.py').read_text(encoding='utf-8')
REMINDERS = (ROOT / 'app' / 'services' / 'reminder_scheduler.py').read_text(encoding='utf-8')
PROCESSOR = (ROOT / 'app' / 'services' / 'notification_processor.py').read_text(encoding='utf-8')
LEADS = (ROOT / 'app' / 'routes' / 'leads.py').read_text(encoding='utf-8')
LEGACY_ROUTES = (ROOT / 'app' / 'routes.py').read_text(encoding='utf-8')


def _get_notifications_body():
    start = APP_INIT.index("def get_notifications():")
    end = APP_INIT.index("@app.route('/api/leads/notifications/mark-read'", start)
    return APP_INIT[start:end]


def _mark_read_body():
    start = APP_INIT.index("def mark_notifications_read():")
    end = APP_INIT.index("@app.route('/api/internal/reminders/process'", start)
    return APP_INIT[start:end]


def test_notification_get_is_read_only_and_worker_free():
    body = _get_notifications_body()
    assert 'process_pending_reminders(' not in body
    assert 'process_notification_queue(' not in body
    assert '.update(' not in body
    assert 'db.session.commit()' not in body
    assert "mode = (_req.args.get('mode')" in body
    assert "after_id = _int_arg('after_id'" in body


def test_notification_get_is_bounded_compact_and_counted():
    body = _get_notifications_body()
    assert "_int_arg('limit', 20, 1, 50)" in body
    assert 'unread_count = base.filter' in body
    assert ".limit(limit)" in body
    assert "'cursor': max_id" in body
    assert "'server_time': _dt.utcnow().isoformat()" in body
    assert "'payload': row.payload" not in body
    assert "'user_id': row.user_id" not in body


def test_mark_read_uses_scoped_bulk_update():
    body = _mark_read_body()
    assert "Notification.query.filter_by(user_id=user.id, is_read=False)" in body
    assert "Notification.tenant_id == user.tenant_id" in body
    assert ".update({'is_read': True, 'read_at': now}" in body
    assert "for row in q.all()" not in body


def test_reminder_processor_is_bounded_and_overlap_guarded():
    assert '_REMINDER_LOCK = threading.Lock()' in REMINDERS
    assert 'if not _REMINDER_LOCK.acquire(blocking=False)' in REMINDERS
    assert 'finally:' in REMINDERS and '_REMINDER_LOCK.release()' in REMINDERS
    assert '.limit(batch_size).all()' in REMINDERS
    assert '.limit(remaining).all()' in REMINDERS
    assert 'joinedload(CallbackReminder.lead)' in REMINDERS
    assert 'process_notification_queue(batch_size=100)' not in REMINDERS


def test_notification_processor_is_deterministic_and_tenant_scoped():
    assert '.order_by(NotificationEvent.scheduled_for.asc(), NotificationEvent.id.asc())' in PROCESSOR
    assert 'subs_query = PushSubscription.query.filter_by(user_id=event.user_id, is_active=True)' in PROCESSOR
    assert 'PushSubscription.tenant_id == event.tenant_id' in PROCESSOR
    assert "NotificationEvent.status == 'queued'" in PROCESSOR


def test_lead_routes_enqueue_without_inline_push_drain():
    assert 'enqueue_lead_assigned' in LEADS
    assert 'enqueue_lead_reassigned' in LEADS
    assert 'process_notification_queue(batch_size=50)' not in LEADS
    assert 'process_notification_queue(batch_size=50)' not in LEGACY_ROUTES
