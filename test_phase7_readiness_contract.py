from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP_INIT = ROOT / "app" / "__init__.py"
VERCEL = ROOT / "vercel.json"


def _text(path):
    return path.read_text(encoding="utf-8")


def test_observability_logs_response_bytes_and_tenant_safe_scope():
    src = _text(APP_INIT)
    assert "def _perf_response_bytes" in src
    assert "def _perf_tenant_scope" in src
    assert "X-Perf-Response-Bytes" in src
    assert "response_bytes={bytes}" in src
    assert "tenant_scope={tenant_scope}" in src
    assert "env={env}" in src
    assert "request.get_json" not in src[src.index("def _register_api_perf"):src.index("def _register_db_perf")]


def test_observability_covers_final_high_read_routes():
    src = _text(APP_INIT)
    for route_key in (
        "dashboard_stats",
        "leads",
        "lead_detail_bundle",
        "action_board",
        "notifications",
        "reports",
        "lead_sources_performance",
        "lead_sources_logs",
        "background_job",
    ):
        assert route_key in src


def test_scheduler_contract_documents_current_cadence():
    cfg = _text(VERCEL)
    # Frequent workers are owned by cron-job.org on the current Vercel plan.
    assert '"/api/internal/reminders/process"' not in cfg
    assert '"/api/cron/drain-notifications"' not in cfg
    assert '"/api/internal/jobs/process"' not in cfg
    assert '"/api/cron/meta-backfill' not in cfg
    assert '"/api/cron/meta-report-sync"' in cfg
    assert '"schedule": "29 18 * * *"' in cfg
