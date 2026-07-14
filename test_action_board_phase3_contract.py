from pathlib import Path


SOURCE = Path(__file__).parent / "app" / "routes" / "leads.py"


def _action_board_source():
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("def action_board():")
    end = source.index("# ---------------------------------------------------------------------------\n# Assign / Reassign", start)
    return source[start:end]


def test_action_board_callbacks_are_sql_ranked_and_paged():
    source = _action_board_source()
    assert "func.row_number().over" in source
    assert "partition_by=CallbackReminder.lead_id" in source
    assert "current_callbacks_q.count()" in source
    assert "overdue_callbacks_q.count()" in source
    assert "all_pending_callbacks" not in source
    assert "_slice_page" not in source


def test_action_board_lead_sections_are_bounded_and_compact():
    source = _action_board_source()
    assert ".offset(start).limit(page_size)" in source
    assert "def _lead_card_dict(lead):" in source
    assert "[l.to_dict()" not in source
    assert "LeadNote.lead_id.in_(list(page_lead_ids))" in source
    assert "joinedload(Lead.project)" in source


def test_action_board_preserves_sections_and_counts():
    source = _action_board_source()
    for key in [
        "today_callbacks",
        "overdue_callbacks",
        "new_leads_today",
        "follow_up",
        "no_answer",
        "warm_leads",
        "hot_leads",
    ]:
        assert key in source
    for count_key in [
        "today_callbacks_count",
        "overdue_count",
        "new_leads_count",
        "follow_up_count",
        "no_answer_count",
        "warm_leads_count",
        "hot_leads_count",
    ]:
        assert count_key in source


def test_action_board_visibility_and_tenant_scope_remain():
    source = _action_board_source()
    assert "get_user_visible_leads(viewing_user)" in source
    assert "CallbackReminder.tenant_id == viewing_user.tenant_id" in source
    assert "view_as" in source
    assert "Permission denied" in source
