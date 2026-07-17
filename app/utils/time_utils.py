"""Shared time utilities for LMS business time."""
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE_NAME = 'Asia/Kolkata'
BUSINESS_TZ = ZoneInfo(BUSINESS_TIMEZONE_NAME)
IST = BUSINESS_TZ


def to_ist_str(dt: datetime) -> str:
    """Return ISO-8601 string in IST (+05:30) for any datetime (UTC-naive assumed UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).isoformat()


def now_ist() -> datetime:
    """Return the current datetime in Asia/Kolkata."""
    return datetime.now(IST)


def parse_business_datetime_to_utc_naive(raw_value) -> datetime:
    """Parse an Asia/Kolkata business datetime and return UTC-naive storage value."""
    if not raw_value:
        raise ValueError('Missing datetime value')
    parsed = datetime.fromisoformat(str(raw_value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BUSINESS_TZ)
    else:
        parsed = parsed.astimezone(BUSINESS_TZ)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def business_date_bounds_utc_naive(date_value=None):
    """Return UTC-naive [start, end) bounds for one Asia/Kolkata business date."""
    if date_value is None:
        local_date = now_ist().date()
    elif isinstance(date_value, datetime):
        local_date = date_value.astimezone(BUSINESS_TZ).date() if date_value.tzinfo else date_value.date()
    else:
        local_date = date_value
    start_local = datetime.combine(local_date, time.min, tzinfo=BUSINESS_TZ)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )
