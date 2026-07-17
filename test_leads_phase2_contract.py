from pathlib import Path


SOURCE = Path(__file__).parent / "app" / "routes" / "leads.py"


def _source():
    return SOURCE.read_text(encoding="utf-8")


def test_leads_page_size_budget_is_bounded():
    source = _source()
    assert "LEADS_DEFAULT_PAGE_SIZE = 50" in source
    assert "LEADS_MAX_PAGE_SIZE = 100" in source
    assert "LEADS_MAX_IDS_REFRESH = 100" in source
    assert "maximum=LEADS_MAX_PAGE_SIZE" in source


def test_interactive_leads_endpoint_contract_is_bounded():
    source = _source()
    assert ".offset((page - 1) * page_size)" in source
    assert ".limit(page_size)" in source
    assert "LEADS_MAX_PAGE_SIZE" in source
    assert "'pagination'" in source
    assert "'server_time'" in source
    assert "'updated_since'" in source
    assert "'ids'" in source


def test_interactive_leads_endpoint_uses_sql_filters():
    source = _source()
    assert "Lead.status == status" in source
    assert "Lead.project_id == int(project_id)" in source
    assert "Lead.source == source" in source
    assert "Lead.assigned_to == int(assigned_to)" in source
    assert "Lead.sales_manager_id == int(sales_manager_id)" in source
    assert "func.lower(func.coalesce(Lead.name" in source
    assert "func.lower(func.coalesce(Project.name" in source
    assert "_apply_lead_source_cutoff_scope(query, user, user.tenant_id)" in source
    assert "business_date_bounds_utc_naive(datetime.strptime(date_from" in source
    assert "business_date_bounds_utc_naive(datetime.strptime(date_to" in source


def test_interactive_leads_list_fields_are_reduced():
    source = _source()
    start = source.index("def lead_list_dict(lead):")
    end = source.index("total_pages =", start)
    list_serializer = source[start:end]
    for heavy_field in [
        "'gclid'",
        "'utm_source'",
        "'utm_medium'",
        "'utm_campaign'",
        "'utm_content'",
        "'utm_term'",
        "'landing_page_url'",
        "'assigned_by'",
        "'created_by'",
    ]:
        assert heavy_field not in list_serializer
