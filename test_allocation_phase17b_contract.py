from pathlib import Path


SOURCE = Path("app/routes/leads.py").read_text(encoding="utf-8")


def test_workload_counts_callbacks_only_for_current_active_assignee():
    assert "CallbackReminder.lead_id == Lead.id" in SOURCE
    assert "Lead.assigned_to == m.id" in SOURCE
    assert "Lead.is_active == True" in SOURCE
    assert "legacy_callback_delta" in SOURCE


def test_workload_preview_and_move_are_bounded_and_revalidated():
    assert "@leads_bp.route('/assign-reassign/workload-preview'" in SOURCE
    assert "selection_mode" in SOURCE
    assert "mode == 'selected'" in SOURCE
    assert "mode == 'current_page'" in SOURCE
    assert "mode == 'random_n'" in SOURCE
    assert "ordered_q.limit(500)" in SOURCE
    assert "lead.assigned_to != from_user.id" in SOURCE
    assert "LeadAssignmentHistory" in SOURCE


def test_workload_move_transfers_pending_callback_owner():
    assert "CallbackReminder.query.filter" in SOURCE
    assert "CallbackReminder.lead_id == lead.id" in SOURCE
    assert "CallbackReminder.status == 'pending'" in SOURCE
    assert "assigned_user_id': to_user.id" in SOURCE


def test_recycle_queue_has_eligibility_reasons_and_read_only_excluded_view():
    assert "def _recycle_eligibility_parts" in SOURCE
    assert "TERMINAL_LEAD_STATUSES" in SOURCE
    assert "PROTECTED_RECYCLE_STATUSES" in SOURCE
    assert "future_pending_callback" in SOURCE
    assert "inside_cooldown" in SOURCE
    assert "view == 'excluded'" in SOURCE


def test_reshuffle_revalidates_selected_leads_before_assignment():
    assert "eligible_q, skip_reasons = _recycle_eligibility_parts(visible, cooldown_days)" in SOURCE
    assert "No eligible leads selected" in SOURCE
    assert "skip_reasons" in SOURCE
