"""Timezone helpers for Skill Orbit India (Indian Standard Time - IST / UTC+05:30).

Provides consistent conversion between stored UTC naive datetimes and user-facing IST.
"""

from datetime import date, datetime, timedelta, timezone

# Indian Standard Time (UTC+05:30) - constant offset, no DST
IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Return current timezone-aware datetime in IST."""
    return datetime.now(IST)


def today_ist() -> date:
    """Return current calendar date in India (IST)."""
    return datetime.now(IST).date()


def to_ist(dt):
    """Convert any datetime (UTC naive or aware) to IST.
    
    If dt is None, returns None.
    If dt has no tzinfo, assumes it was stored as UTC naive and converts to IST.
    """
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    if not isinstance(dt, datetime):
        return dt

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def from_ist(dt):
    """Convert an IST datetime (e.g. from datetime-local user input) to UTC naive for storage."""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    if not isinstance(dt, datetime):
        return dt

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.replace(tzinfo=None)


def format_ist(dt, fmt="%I:%M %p") -> str:
    """Jinja filter to convert a stored UTC datetime to IST and format it.
    
    If dt is None, returns '—'.
    """
    if dt is None:
        return "—"
    ist_dt = to_ist(dt)
    if not ist_dt:
        return "—"
    return ist_dt.strftime(fmt)


def format_ist_datetime(dt, fmt="%Y-%m-%d %H:%M") -> str:
    """Jinja filter for admin tables, formatting as YYYY-MM-DD HH:MM in IST."""
    return format_ist(dt, fmt=fmt)
