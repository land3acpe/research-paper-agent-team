"""Run-level summary models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["running", "success", "failed", "partial"]


class SourceResult(BaseModel):
    source: str
    query: str
    raw_count: int = 0
    normalized_count: int = 0
    errors: list[str] = Field(default_factory=list)


class RunSummary(BaseModel):
    run_id: str
    started_at: str
    ended_at: str | None = None
    status: RunStatus
    sources: list[SourceResult] = Field(default_factory=list)
    raw_count: int = 0
    normalized_count: int = 0
    deduped_count: int = 0
    filtered_count: int = 0
    failed_count: int = 0
    report_path: str | None = None
    log_path: str | None = None
    errors: list[str] = Field(default_factory=list)
    dry_run: bool = False
