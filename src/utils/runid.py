"""Run ID generation and parsing.

Format: {profile_slug}-{schedule_mode}-{YYYYMMDD-HHMMSS}-{shortuuid8}
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import shortuuid

ScheduleMode = Literal["daily", "weekly", "monthly", "manual"]

_PATTERN = re.compile(
    r"^(?P<slug>[a-z0-9-]+)-"
    r"(?P<mode>daily|weekly|monthly|manual)-"
    r"(?P<date>\d{8})-(?P<time>\d{6})-"
    r"(?P<short>[a-z0-9]{8})$"
)


@dataclass(frozen=True)
class RunIdParts:
    profile_slug: str
    schedule_mode: str
    timestamp: datetime
    short_id: str


def generate_run_id(
    profile_slug: str,
    schedule_mode: ScheduleMode,
    now: datetime | None = None,
) -> str:
    if now is None:
        now = datetime.now(UTC)
    ts = now.strftime("%Y%m%d-%H%M%S")
    short = shortuuid.uuid()[:8].lower()
    return f"{profile_slug}-{schedule_mode}-{ts}-{short}"


def parse_run_id(run_id: str) -> RunIdParts:
    m = _PATTERN.match(run_id)
    if not m:
        raise ValueError(f"invalid run_id: {run_id}")
    ts = datetime.strptime(
        f"{m['date']}{m['time']}", "%Y%m%d%H%M%S"
    ).replace(tzinfo=UTC)
    return RunIdParts(
        profile_slug=m["slug"],
        schedule_mode=m["mode"],
        timestamp=ts,
        short_id=m["short"],
    )
