from pathlib import Path


ROOT = Path(__file__).resolve().parent
SERVICE = ROOT / 'app' / 'services' / 'analytics.py'
ROUTES = ROOT / 'app' / 'routes' / 'reports.py'


def _text(path):
    return path.read_text(encoding='utf-8')


def test_phase10_uses_existing_transactional_entities_only():
    source = _text(SERVICE)
    assert 'class AnalyticsService' in source
    assert 'db.Model' not in source
    for entity in (
        'PipelineTransition', 'Lead', 'OrganisationUnit', 'Project',
        'Location', 'Visit', 'MeetingRoom', 'ChannelPartner', 'ActionItem',
    ):
        assert entity in source


def test_phase10_interactive_reports_are_bounded_sql_aggregates():
    source = _text(SERVICE)
    assert 'MAX_INTERACTIVE_ROWS = 100' in source
    assert 'MAX_DATE_SPAN_DAYS = 366' in source
    assert '.group_by(' in source
    assert 'func.count(' in source
    assert 'rows[:self.filters.limit]' in source
    assert 'Lead.query.all()' not in source
    assert 'Visit.query.all()' not in source
    assert 'ActionItem.query.all()' not in source


def test_phase10_routes_enforce_view_and_export_capabilities():
    source = _text(ROUTES)
    assert "@reports_bp.get('/v2/filters')" in source
    assert "@reports_bp.get('/v2/<string:report_key>')" in source
    assert "@reports_bp.get('/v2/<string:report_key>/export')" in source
    assert "@require_capability('reports.view', 'OWN')" in source
    assert "@require_capability('reports.export', 'OWN')" in source


def test_phase10_export_is_separate_and_aggregate_only():
    source = _text(SERVICE)
    assert 'def analytics_workbook(payload)' in source
    assert "payload.get('rows', [])" in source
    assert 'MAX_EXPORT_ROWS = 5000' in source
    assert 'lead.name' not in source.lower()
    assert 'lead.phone' not in source.lower()


def test_phase10_covers_all_approved_report_families():
    source = _text(SERVICE)
    for report in (
        '_report_pipeline', '_report_leads', '_report_organisations',
        '_report_users', '_report_projects', '_report_locations',
        '_report_visits', '_report_reception', '_report_meeting_rooms',
        '_report_channel_partners', '_report_action_items',
    ):
        assert f'def {report}' in source
