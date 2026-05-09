from datetime import datetime, timezone

from src.utils.time import compute_window, format_iso_date


def test_compute_window_basic():
    now = datetime(2026, 5, 10, tzinfo=timezone.utc)
    start, end = compute_window(days=14, now=now)
    assert end == now
    assert (end - start).days == 14


def test_compute_window_with_overlap():
    now = datetime(2026, 5, 10, tzinfo=timezone.utc)
    start, end = compute_window(days=14, overlap_days=2, now=now)
    assert (end - start).days == 16


def test_format_iso_date():
    d = datetime(2026, 5, 10, 9, 30, tzinfo=timezone.utc)
    assert format_iso_date(d) == "2026-05-10"
