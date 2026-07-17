from pathlib import Path


ROOT = Path(__file__).resolve().parent
LEAD_SOURCES = ROOT / "app" / "routes" / "lead_sources.py"
VERCEL = ROOT / "vercel.json"


def _text(path):
    return path.read_text(encoding="utf-8")


def test_lms_performance_endpoint_is_source_form_only():
    src = _text(LEAD_SOURCES)
    assert "def _build_lms_source_form_performance" in src
    assert "def report_performance" in src
    performance_section = src[src.index("def report_performance"):src.index("@lead_sources_bp.route('/reports/sync-meta'")]
    assert "_build_lms_source_form_performance" in performance_section
    assert "_build_performance_report" not in performance_section
    assert "'form_rows': form_rows" in performance_section
    assert "'campaign_rows': []" in performance_section
    assert "'report_scope': 'source_form'" in performance_section


def test_lms_snapshot_fields_and_cpl_contract():
    src = _text(LEAD_SOURCES)
    report_builder = src[src.index("def _build_lms_source_form_performance"):src.index("def _build_source_report_rows")]
    for field in (
        "source_name",
        "source_added_at",
        "last_sync",
        "form_name",
        "spend",
        "total_leads",
        "unique_leads",
        "processed",
        "duplicate",
        "errors",
        "conversion_rate",
        "cpl",
    ):
        assert field in report_builder
    assert "float(bucket['spend']) / float(unique)" in report_builder
    assert "if effective_status not in {'processed', 'duplicate', 'error'}" in report_builder
    assert "elif effective_status == 'duplicate':\n                bucket['total_leads'] += 1" in report_builder
    assert "elif effective_status == 'error':\n                bucket['total_leads'] += 1" in report_builder


def test_source_cards_expose_submission_and_lms_lead_counts():
    src = _text(LEAD_SOURCES)
    list_section = src[src.index("def _ingestion_submission_counts_by_source_id"):src.index("def create_source")]
    assert "item['ingestion_events_count']" in list_section
    assert "item['processed_events_count']" in list_section
    assert "item['duplicate_events_count']" in list_section
    assert "item['error_events_count']" in list_section
    assert "item['lms_leads_count']" in list_section
    assert "item['total_leads_ingested'] = item['ingestion_events_count']" in list_section


def test_source_performance_exports_use_canonical_lms_report_builder():
    src = _text(LEAD_SOURCES)
    csv_section = src[src.index("def report_by_source_export_csv"):src.index("@lead_sources_bp.route('/reports/by-source/export.xlsx'")]
    xlsx_section = src[src.index("def report_by_source_export_xlsx"):src.index("@lead_sources_bp.route('/reports/attribution/export.csv'")]
    for section in (csv_section, xlsx_section):
        assert "_build_lms_source_form_performance" in section
        assert "_build_performance_report" not in section
        assert "'total_leads'" in section
        assert "'unique_leads'" in section


def test_meta_report_sync_fetches_spend_only():
    src = _text(LEAD_SOURCES)
    sync = src[src.index("def _sync_meta_report_snapshots"):src.index("def _cleanup_validation_leads")]
    assert "_fetch_meta_source_spend" in sync
    assert "_build_performance_report" not in sync
    assert "'scope': 'source_form_spend'" in sync
    for forbidden in ("ctr", "cpc", "cpm", "reach", "impressions", "clicks", "cost_per_action_type"):
        assert forbidden not in sync


def test_meta_report_sync_matches_known_campaigns_before_account_fallback():
    src = _text(LEAD_SOURCES)
    assert "def _source_campaign_ids_for_spend" in src
    assert "def _fetch_meta_source_spend" in src
    assert "'level': 'campaign'" in src
    assert "'campaign_id,campaign_name,spend'" in src
    sync = src[src.index("def _sync_meta_report_snapshots"):src.index("def _cleanup_validation_leads")]
    assert "_source_campaign_ids_for_spend" in sync
    assert "'source_spend_method': spend_result.get('method')" in sync
    assert "'account_total_all'" in src
    assert "latest_source_level_spend_by_source" in src


def test_daily_spend_cron_is_1159_pm_ist():
    cfg = _text(VERCEL)
    assert '"/api/cron/meta-report-sync"' in cfg
    assert '"schedule": "29 18 * * *"' in cfg


def test_required_operational_routes_are_still_present():
    src = _text(LEAD_SOURCES)
    for route in (
        "/meta/pull-recent",
        "/meta/page-forms",
        "/meta/save-connection",
        "/google/save-connection",
        "/logs",
        "/forms/mappings",
    ):
        assert route in src
