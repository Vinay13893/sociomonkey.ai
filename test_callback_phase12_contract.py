from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(rel_path):
    return (ROOT / rel_path).read_text(encoding='utf-8')


def test_business_timezone_standard_is_asia_kolkata():
    src = read('app/utils/time_utils.py')
    assert "BUSINESS_TIMEZONE_NAME = 'Asia/Kolkata'" in src
    assert 'ZoneInfo(BUSINESS_TIMEZONE_NAME)' in src
    assert 'Asia/Calcutta' not in src
    assert 'business_date_bounds_utc_naive' in src


def test_action_board_uses_ist_boundaries_and_due_now_overdue_split():
    src = read('app/routes/leads.py')
    assert 'today_ist = now_ist().date()' in src
    assert 'today_start, today_end = business_date_bounds_utc_naive(today_ist)' in src
    assert 'CallbackReminder.callback_datetime >= datetime.utcnow()' in src
    assert 'CallbackReminder.callback_datetime < datetime.utcnow()' in src
    assert 'order_by=(CallbackReminder.callback_datetime.asc(), CallbackReminder.id.asc())' in src
    assert "selected_from_date.isoformat()" in src
    assert "selected_to_date.isoformat()" in src


def test_callback_workflow_is_canonical_and_one_pending():
    src = read('app/services/callback_workflow.py')
    assert 'def find_pending_callback' in src
    assert "filter_by(lead_id=lead_id, status='pending')" in src
    assert 'order_by(CallbackReminder.callback_datetime.asc(), CallbackReminder.id.asc())' in src
    assert 'def create_callback_for_lead' in src
    assert 'assigned_user_id = resolve_callback_owner(lead, actor)' in src
    assert 'if existing:' in src
    assert 'CALLBACK_PENDING_ERROR' in src


def test_reschedule_resets_reminder_flags():
    src = read('app/services/callback_workflow.py')
    assert 'def reschedule_callback' in src
    assert 'callback.reminder_10_sent = False' in src
    assert 'callback.reminder_due_sent = False' in src


def test_routes_use_callback_workflow_helpers():
    src = read('app/routes/leads.py')
    assert 'create_callback_for_lead(' in src
    assert 'reschedule_callback(' in src
    assert 'complete_callback_record(cb, user, closure_note)' in src
    assert 'cancel_callback_record(cb, user, closure_note)' in src
    assert "'pending_callback': existing_pending.to_dict()" in src
    assert '), 409' in src


def test_reminder_processor_does_not_permanently_miss_due_callbacks():
    src = read('app/services/reminder_scheduler.py')
    assert 'grace_window_due' not in src
    assert 'CallbackReminder.callback_datetime <= one_min_from_now' in src
    assert 'CallbackReminder.callback_datetime >= grace_window_due' not in src


def test_call_started_does_not_auto_complete_callback():
    src = read('app/routes/leads.py')
    start = src.index("def log_call_activity")
    end = src.index("@leads_bp.route('/<int:lead_id>/activity-timeline'", start)
    body = src[start:end]
    assert "CallbackReminder.status = 'completed'" not in body
    assert 'complete_callback_record' not in body


def test_frontend_refreshes_action_board_after_callback_mutations():
    frontend = ROOT.parent / 'frontend_static'
    if not frontend.exists():
        frontend = ROOT.parent / 'frontend-final-freeze'
    leads_js = (frontend / 'src/products/lms/leads.js').read_text(encoding='utf-8')
    action_board_js = (frontend / 'src/products/lms/action-board.js').read_text(encoding='utf-8')
    assert 'function _abRefreshPreservingState()' in action_board_js
    assert "window._ACTIVE_ROUTE === 'action_board'" in leads_js
    assert '_abRefreshPreservingState' in leads_js
