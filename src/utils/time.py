"""Time window utilities for paper discovery."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def compute_window(
    days: int,
    overlap_days: int = 0,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Return (start, end) datetimes for a discovery window.

    Window length = days + overlap_days, ending at `now`.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    start = now - timedelta(days=days + overlap_days)
    return start, now


def format_iso_date(dt: datetime) -> str:
    """YYYY-MM-DD."""
    return dt.strftime("%Y-%m-%d")
