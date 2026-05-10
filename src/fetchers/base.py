"""Fetcher abstract base + result DTO."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.models.paper import PaperCandidate


@dataclass
class FetchResult:
    source: str
    query: str
    raw_count: int = 0
    normalized_count: int = 0
    candidates: list[PaperCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_payload: Any | None = None  # for dumping to data/raw/


class FetcherBase(ABC):
    source_name: str = "abstract"

    @abstractmethod
    def fetch(
        self,
        query: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> FetchResult: ...

    @abstractmethod
    def parse_response(self, payload: Any) -> list[PaperCandidate]: ...
