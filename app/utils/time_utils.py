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


def parse_business_date(value):
    """Parse a YYYY-MM-DD business date without silently treating it as UTC."""
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.astimezone(BUSINESS_TZ).date() if value.tzinfo else value.date()
    if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
        return value
    return datetime.strptime(str(value).strip(), '%Y-%m-%d').date()


def business_date_range_utc_naive(date_from=None, date_to=None):
    """Return UTC-naive [start, end) bounds for inclusive IST calendar dates."""
    start = end = None
    from_date = parse_business_date(date_from)
    to_date = parse_business_date(date_to)
    if from_date is not None:
        start, _ = business_date_bounds_utc_naive(from_date)
    if to_date is not None:
        _, end = business_date_bounds_utc_naive(to_date)
    return start, end


def utc_naive_to_business_datetime(value):
    """Convert a UTC-naive storage datetime to an aware Asia/Kolkata datetime."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BUSINESS_TZ)
