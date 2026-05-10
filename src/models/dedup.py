"""DedupCandidate model for soft-duplicate review queue."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

DedupStatus = Literal["pending", "merged", "rejected"]
MatchType = Literal["title_hash", "fuzzy_title", "title_author_year"]


class DedupCandidate(BaseModel):
    paper_id_a: int
    paper_id_b: int
    match_type: MatchType
    similarity: float
    status: DedupStatus = "pending"
    resolved_by: str | None = None
    resolved_at: str | None = None
