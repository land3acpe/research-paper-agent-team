"""PaperCandidate model."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PaperCandidate(BaseModel):
    source: str
    source_id: str | None = None
    doi: str | None = None
    title: str
    normalized_title: str | None = None
    title_hash: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    published_date: str | None = None
    indexed_date: str | None = None
    abstract: str | None = None
    keywords: list[str] = Field(default_factory=list)
    url: str | None = None
    pdf_url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
