from datetime import datetime

from app.routes.lead_sources import _parse_report_datetime, _report_date_to_exclusive
from app.routes.reports import _resolve_date_window
from app.utils.time_utils import (
    business_date_range_utc_naive,
    utc_naive_to_business_datetime,
)


def test_ist_calendar_day_maps_to_correct_utc_storage_window():
    start, end = business_date_range_utc_naive('2026-08-23', '2026-08-23')

    assert start == datetime(2026, 8, 22, 18, 30)
    assert end == datetime(2026, 8, 23, 18, 30)


def test_report_helpers_share_the_same_inclusive_ist_window():
    expected_start = datetime(2026, 8, 22, 18, 30)
    expected_end = datetime(2026, 8, 23, 18, 30)

    assert _resolve_date_window('', '2026-08-23', '2026-08-23') == (
        expected_start,
        expected_end,
    )
    assert _parse_report_datetime('2026-08-23') == expected_start
    assert _report_date_to_exclusive('2026-08-23') == expected_end


def test_meta_utc_timestamp_is_assigned_to_its_ist_business_date():
    meta_created_at = datetime(2026, 8, 22, 20, 0)

    converted = utc_naive_to_business_datetime(meta_created_at)

    assert converted.isoformat() == '2026-08-23T01:30:00+05:30'
    assert converted.date().isoformat() == '2026-08-23'
