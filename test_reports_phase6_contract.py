from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "app" / "routes" / "reports.py"
LEAD_SOURCES = ROOT / "app" / "routes" / "lead_sources.py"


def _text(path):
    return path.read_text(encoding="utf-8")


def _section(src, start, end):
    return src[src.index(start):src.index(end)]


def test_interactive_lead_report_uses_sql_aggregation_not_full_rows():
    src = _text(REPORTS)
    body = _section(src, "def lead_report():", "@reports_bp.route('/team'")
    assert ".subquery()" in body
    assert "func.count(report_sq.c.id)" in body
    assert "group_by(func.coalesce(report_sq.c.status" in body
    assert "group_by(func.coalesce(report_sq.c.source" in body
    assert "outerjoin(Project" in body
    assert "leads = query.all()" not in body
    assert "for lead in leads" not in body


def test_comparison_period_metrics_do_not_materialize_visible_ids():
    src = _text(REPORTS)
    body = _section(src, "def _period_metrics", "def _build_comparison_payload")
    assert ".with_entities(Lead.id).subquery()" in body
    assert "visible_ids = [r[0]" not in body


def test_team_report_uses_one_grouped_lead_aggregate():
    src = _text(REPORTS)
    body = _section(src, "def team_report():", "@reports_bp.route('/comparison'")
    assert "group_by(Lead.assigned_to)" in body
    assert "func.sum(case(" in body
    assert "lead_stats" in body
    assert "leads = q.all()" not in body
    assert "sum(1 for l in leads" not in body


def test_activity_summary_uses_grouped_queries():
    src = _text(REPORTS)
    body = _section(src, "def activity_report():", "@reports_bp.route('/activity-logs'")
    assert "group_by(User.name)" in body
    assert "group_by(ActivityLog.action)" in body
    assert "group_by(ActivityLog.module)" in body
    assert "group_by(func.date(ActivityLog.created_at))" in body
    assert "for log in ActivityLog.query.all()" not in body


def test_activity_logs_are_paginated_and_compact():
    src = _text(REPORTS)
    body = _section(src, "def get_activity_logs():", "@reports_bp.route('/activity-logs/download'")
    assert ".offset((page - 1) * per_page)" in body
    assert ".limit(per_page)" in body
    assert ".with_entities(" in body
    assert "_compact_activity_row" in body
    assert "old_value" not in body
    assert "new_value" not in body
    assert "[l.to_dict() for l in logs]" not in body


def test_exports_remain_separate_explicit_downloads():
    src = _text(REPORTS)
    for route in (
        "/activity-logs/download",
        "/leads/download",
        "/team/download",
        "/management/download",
        "/activity/download",
    ):
        assert route in src
    assert "send_file(" in src


def test_meta_spend_is_source_level_not_form_level():
    src = _text(LEAD_SOURCES)
    builder = _section(src, "def _build_lms_source_form_performance", "def _build_source_report_rows")
    assert "form_rows.append(finalize(bucket, None, None))" in builder
    assert "latest_source_spend_by_source" in builder
    assert "'fields': 'spend'" in src
    sync = _section(src, "def _sync_meta_report_snapshots", "def _cleanup_validation_leads")
    assert "form_id=''" in sync
    assert "form_name='All Forms'" in sync
