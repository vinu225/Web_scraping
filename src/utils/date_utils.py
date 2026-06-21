"""
src/utils/date_utils.py
========================
Robust date/time parsing helpers that handle the wide variety of formats
encountered across news APIs, RSS feeds, and raw HTML metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from dateutil import parser as dateutil_parser
from dateutil.tz import tzutc


def parse_date(value: str | datetime | None) -> Optional[datetime]:
    """
    Parse a date string into a timezone-aware UTC ``datetime``.

    Accepts ISO 8601, RFC 2822, and many informal formats via ``dateutil``.

    Parameters
    ----------
    value:
        A date string, an already-parsed ``datetime``, or ``None``.

    Returns
    -------
    Optional[datetime]
        UTC-aware datetime, or ``None`` if parsing fails.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = dateutil_parser.parse(value, fuzzy=True)
        return _ensure_utc(dt)
    except (ValueError, OverflowError):
        return None


def _ensure_utc(dt: datetime) -> datetime:
    """Attach UTC timezone if the datetime is naive, otherwise convert."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utcnow() -> datetime:
    """Return the current UTC datetime (always timezone-aware)."""
    return datetime.now(tz=timezone.utc)


def format_iso(dt: Optional[datetime]) -> Optional[str]:
    """Serialise a datetime to an ISO 8601 string, or ``None`` if absent."""
    if dt is None:
        return None
    return dt.isoformat()


def is_recent(dt: Optional[datetime], days: int = 30) -> bool:
    """
    Return ``True`` if ``dt`` falls within the last ``days`` days.

    Parameters
    ----------
    dt:
        Datetime to check (may be ``None``).
    days:
        Window in days (default 30).
    """
    if dt is None:
        return False
    delta = utcnow() - _ensure_utc(dt)
    return delta.days <= days
