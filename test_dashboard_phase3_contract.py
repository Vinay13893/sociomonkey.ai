from pathlib import Path


SOURCE = Path(__file__).parent / "app" / "routes" / "leads.py"


def _dashboard_source():
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index("def dashboard_stats():")
    end = source.index("# ---------------------------------------------------------------------------\n# Daily Action Board", start)
    return source[start:end]


def test_dashboard_uses_sql_aggregation_not_raw_lead_lists():
    source = _dashboard_source()
    assert ".group_by(Lead.status)" in source
    assert ".group_by(func.coalesce(Lead.source" in source
    assert ".group_by(Lead.project_id, Lead.status)" in source
    assert "with_entities(func.count(Lead.id))" in source
    assert "scoped_leads =" not in source
    assert "[l.to_dict()" not in source


def test_dashboard_preserves_role_and_tenant_scope():
    source = _dashboard_source()
    assert "tenant_id=tid_scope" in source
    assert "Lead.tenant_id == tid_scope" in source
    assert "Lead.assigned_to == user.id" in source
    assert "Lead.sales_manager_id == user.id" in source
    assert "apply_test_lead_filter(q)" in source
    assert "_apply_lead_source_cutoff_scope(q, user, tid_scope)" in source


def test_dashboard_filters_are_sql_side():
    source = _dashboard_source()
    assert "Lead.project_id == int(project_id)" in source
    assert "Lead.created_at >=" in source
    assert "Lead.created_at <" in source
    assert "Lead.source == source" in source
    assert "Lead.status == status" in source
    assert "Lead.assigned_to == int(assigned_to)" in source
    assert "business_date_bounds_utc_naive" in source
