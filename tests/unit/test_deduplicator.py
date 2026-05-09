"""Tests for the deduplication orchestrator."""
import pytest

from src.dedupe.deduplicator import deduplicate
from src.models.paper import PaperCandidate
from src.normalize.normalizer import normalize_paper
from src.storage.db import apply_migrations, open_db
from src.storage.repositories import DedupCandidatesRepo, PapersRepo


@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "t.db")
    apply_migrations(c)
    yield c
    c.close()


def _norm(title: str, **kw) -> PaperCandidate:
    return normalize_paper(PaperCandidate(source="crossref", title=title, **kw))


def test_deduplicate_hard_removes_duplicates(conn):
    papers = [
        _norm("X", doi="10.1/a"),
        _norm("X", doi="10.1/a"),
        _norm("Y", doi="10.2/b"),
    ]
    result = deduplicate(papers, conn=conn)
    assert len(result.unique) == 2


def test_deduplicate_soft_writes_candidates(conn):
    p1 = _norm("Harmonic Current Suppression in PMSM")
    p2 = _norm("harmonic current suppression in pmsm")
    PapersRepo(conn).insert(p1)
    PapersRepo(conn).insert(p2)
    deduplicate([p1, p2], conn=conn)
    candidates = DedupCandidatesRepo(conn).list_pending()
    assert len(candidates) >= 1
