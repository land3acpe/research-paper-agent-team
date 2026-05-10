import sqlite3
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.models.paper import PaperCandidate
from src.models.run import RunSummary
from src.storage.db import apply_migrations, open_db
from src.storage.repositories import (
    DedupCandidatesRepo,
    FilterDecisionsRepo,
    PapersRepo,
    RunsRepo,
)


@pytest.fixture
def conn(tmp_path: Path) -> Generator[sqlite3.Connection, None, None]:
    c = open_db(tmp_path / "t.db")
    apply_migrations(c)
    yield c
    c.close()


def test_papers_insert_and_lookup_by_doi(conn: sqlite3.Connection) -> None:
    repo = PapersRepo(conn)
    p = PaperCandidate(source="crossref", title="X", doi="10.1/abc", title_hash="h1")
    pid = repo.insert(p, run_id="r1")
    row = repo.get_by_doi("10.1/abc")
    assert row is not None
    assert row["id"] == pid


def test_papers_lookup_by_title_hash(conn: sqlite3.Connection) -> None:
    repo = PapersRepo(conn)
    p = PaperCandidate(source="crossref", title="X", title_hash="h2")
    repo.insert(p, run_id="r2")
    assert repo.get_by_title_hash("h2") is not None
    assert repo.get_by_title_hash("missing") is None


def test_papers_lookup_by_source_id(conn: sqlite3.Connection) -> None:
    repo = PapersRepo(conn)
    p = PaperCandidate(source="arxiv", source_id="2305.99999", title="X", title_hash="h3")
    repo.insert(p, run_id="r3")
    assert repo.get_by_source_id("arxiv", "2305.99999") is not None


def test_papers_list_by_run_filters(conn: sqlite3.Connection) -> None:
    repo = PapersRepo(conn)
    p1 = PaperCandidate(source="crossref", title="A", doi="10.1/a", title_hash="h1")
    p2 = PaperCandidate(source="crossref", title="B", doi="10.2/b", title_hash="h2")
    repo.insert(p1, run_id="r1")
    repo.insert(p2, run_id="r2")
    r1_papers = repo.list_by_run("r1")
    assert len(r1_papers) == 1
    assert r1_papers[0]["doi"] == "10.1/a"


def test_runs_insert_and_get(conn: sqlite3.Connection) -> None:
    repo = RunsRepo(conn)
    summary = RunSummary(
        run_id="rid-1",
        started_at=datetime.now(UTC).isoformat(),
        status="running",
    )
    repo.insert(summary, profile_slug="dtp-pmsm", schedule_mode="weekly")
    got = repo.get_by_run_id("rid-1")
    assert got is not None
    assert got["run_id"] == "rid-1"


def test_runs_update_summary(conn: sqlite3.Connection) -> None:
    repo = RunsRepo(conn)
    s = RunSummary(run_id="rid-1", started_at="2026-05-10T00:00:00+00:00", status="running")
    repo.insert(s, profile_slug="dtp-pmsm", schedule_mode="weekly")
    s.status = "success"
    s.raw_count = 10
    s.ended_at = "2026-05-10T00:01:00+00:00"
    repo.update_summary(s)
    got = repo.get_by_run_id("rid-1")
    assert got is not None
    assert got["status"] == "success"
    assert got["raw_count"] == 10


def test_filter_decisions_log(conn: sqlite3.Connection) -> None:
    repo = FilterDecisionsRepo(conn)
    repo.log(run_id="rid-1", paper_id=42, decision="reject", reason_code="missing_abstract", reason_text="no abstract")
    rows = repo.list_by_run("rid-1")
    assert len(rows) == 1
    assert rows[0]["reason_code"] == "missing_abstract"


def test_dedup_candidate_insert(conn: sqlite3.Connection) -> None:
    repo = DedupCandidatesRepo(conn)
    repo.insert(paper_id_a=1, paper_id_b=2, match_type="fuzzy_title", similarity=0.95)
    rows = repo.list_pending()
    assert len(rows) == 1
