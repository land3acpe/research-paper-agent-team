import re
from datetime import UTC, datetime

import pytest

from src.utils.runid import generate_run_id, parse_run_id

RUN_ID_PATTERN = re.compile(r"^[a-z0-9-]+-(daily|weekly|monthly|manual)-\d{8}-\d{6}-[a-z0-9]{8}$")


def test_generate_run_id_format():
    rid = generate_run_id(profile_slug="dtp-pmsm", schedule_mode="weekly")
    assert RUN_ID_PATTERN.match(rid), f"unexpected format: {rid}"


def test_generate_run_id_unique():
    rids = {generate_run_id("dtp-pmsm", "weekly") for _ in range(100)}
    assert len(rids) == 100


def test_generate_run_id_uses_timestamp():
    fixed = datetime(2026, 5, 10, 9, 0, 0, tzinfo=UTC)
    rid = generate_run_id("dtp-pmsm", "weekly", now=fixed)
    assert "20260510-090000" in rid


def test_parse_run_id_roundtrip():
    rid = "dtp-pmsm-weekly-20260510-090000-a1b2c3d4"
    parsed = parse_run_id(rid)
    assert parsed.profile_slug == "dtp-pmsm"
    assert parsed.schedule_mode == "weekly"
    assert parsed.timestamp.year == 2026
    assert parsed.short_id == "a1b2c3d4"


def test_parse_run_id_invalid():
    with pytest.raises(ValueError):
        parse_run_id("invalid-format")
