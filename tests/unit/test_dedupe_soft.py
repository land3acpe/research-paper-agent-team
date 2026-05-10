"""Tests for soft deduplication (title_hash, fuzzy_title, title_author_year)."""

from src.dedupe.soft import find_soft_matches
from src.models.paper import PaperCandidate
from src.normalize.normalizer import normalize_paper


def _make(
    title: str, authors: list[str] | None = None, year: str | None = "2024"
) -> PaperCandidate:
    return normalize_paper(
        PaperCandidate(
            source="crossref",
            title=title,
            authors=authors or [],
            published_date=f"{year}-01-01" if year else None,
        )
    )


def test_title_hash_match():
    p1 = _make("Harmonic Current Suppression")
    p2 = _make("harmonic current suppression!")
    matches = find_soft_matches([p1, p2], threshold=90.0)
    assert len(matches) == 1
    assert matches[0].match_type == "title_hash"


def test_fuzzy_title_match():
    p1 = _make("Harmonic current suppression in dual three-phase PMSM drives")
    p2 = _make("Harmonic current suppression in dual three-phase PMSM drive")
    matches = find_soft_matches([p1, p2], threshold=90.0)
    assert len(matches) == 1
    assert matches[0].match_type == "fuzzy_title"


def test_no_match_below_threshold():
    p1 = _make("Topic A")
    p2 = _make("Topic B")
    matches = find_soft_matches([p1, p2], threshold=90.0)
    assert matches == []


def test_title_author_year_match():
    p1 = _make("Some title", authors=["A. Author"], year="2024")
    p2 = _make("Some title with extra words really different", authors=["A. Author"], year="2024")
    matches = find_soft_matches([p1, p2], threshold=85.0, title_author_year=True)
    assert len(matches) >= 1
