"""Shared time utilities — IST helpers."""
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def to_ist_str(dt: datetime) -> str:
    """Return ISO-8601 string in IST (+05:30) for any datetime (UTC-naive assumed UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).isoformat()


def now_ist() -> datetime:
    """Return the current datetime in IST (timezone-aware)."""
    return datetime.now(IST)
