"""Soft deduplication via title hash, fuzzy title match, and (title, author, year) combinations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz

from src.models.paper import PaperCandidate


@dataclass(frozen=True)
class SoftMatch:
    idx_a: int
    idx_b: int
    match_type: Literal["title_hash", "fuzzy_title", "title_author_year"]
    similarity: float


def _first_author_lastname(authors: list[str]) -> str | None:
    if not authors:
        return None
    return authors[0].split()[-1].lower()


def _year(date: str | None) -> str | None:
    return date[:4] if date and len(date) >= 4 else None


def find_soft_matches(
    papers: list[PaperCandidate],
    threshold: float = 90.0,
    title_author_year: bool = True,
) -> list[SoftMatch]:
    matches: list[SoftMatch] = []
    n = len(papers)
    for i in range(n):
        a = papers[i]
        for j in range(i + 1, n):
            b = papers[j]
            # 1. title_hash exact match
            if a.title_hash and b.title_hash and a.title_hash == b.title_hash:
                matches.append(SoftMatch(i, j, "title_hash", 100.0))
                continue
            # 2. fuzzy title
            if a.normalized_title and b.normalized_title:
                sim = fuzz.token_set_ratio(a.normalized_title, b.normalized_title)
                if sim >= threshold:
                    matches.append(SoftMatch(i, j, "fuzzy_title", float(sim)))
                    continue
            # 3. title prefix + first author lastname + year
            if title_author_year:
                la = _first_author_lastname(a.authors)
                lb = _first_author_lastname(b.authors)
                ya = _year(a.published_date)
                yb = _year(b.published_date)
                if la and lb and la == lb and ya and yb and ya == yb:
                    if a.normalized_title and b.normalized_title:
                        prefix_sim = fuzz.partial_ratio(
                            a.normalized_title[:40], b.normalized_title[:40]
                        )
                        if prefix_sim >= 80:
                            matches.append(SoftMatch(i, j, "title_author_year", float(prefix_sim)))
    return matches
