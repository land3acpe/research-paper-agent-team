from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models.dedup import DedupCandidate
from src.models.paper import PaperCandidate
from src.models.run import RunSummary, SourceResult


def test_paper_candidate_minimal():
    p = PaperCandidate(source="crossref", title="A title")
    assert p.title == "A title"
    assert p.authors == []
    assert p.doi is None


def test_paper_candidate_with_all_fields():
    p = PaperCandidate(
        source="arxiv",
        source_id="2305.12345",
        doi="10.48550/arXiv.2305.12345",
        title="x",
        authors=["A. B."],
        venue="arXiv",
        published_date="2026-04-01",
        abstract="abstract",
        keywords=["k1"],
        url="https://example.com",
    )
    assert p.source == "arxiv"


def test_paper_candidate_requires_title():
    with pytest.raises(ValidationError):
        PaperCandidate(source="crossref")


def test_run_summary_defaults():
    s = RunSummary(
        run_id="x", started_at=datetime.now(UTC).isoformat(), status="running"
    )
    assert s.raw_count == 0
    assert s.errors == []


def test_source_result_minimal():
    r = SourceResult(source="crossref", query="x", raw_count=10, normalized_count=8)
    assert r.errors == []


def test_dedup_candidate():
    d = DedupCandidate(
        paper_id_a=1, paper_id_b=2, match_type="fuzzy_title", similarity=0.92
    )
    assert d.status == "pending"
