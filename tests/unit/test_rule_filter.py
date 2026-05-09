import pytest

from src.config import RuleFilterSpec
from src.models.paper import PaperCandidate
from src.storage.db import open_db, apply_migrations
from src.storage.repositories import FilterDecisionsRepo
from src.filter.rule_filter import apply_rule_filter


@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "t.db")
    apply_migrations(c)
    yield c
    c.close()


def _p(**kw) -> PaperCandidate:
    return PaperCandidate(source="crossref", title=kw.pop("title", "x"), **kw)


def test_rule_filter_passes_clean_paper(conn):
    spec = RuleFilterSpec(require_year_after=2018, require_abstract=True, blacklist_keywords=[])
    p = _p(title="ok", abstract="abs", published_date="2024-01-01")
    out = apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    assert len(out) == 1


def test_rule_filter_rejects_old_year(conn):
    spec = RuleFilterSpec(require_year_after=2018, require_abstract=False)
    p = _p(title="old", abstract="x", published_date="2010-01-01")
    out = apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    assert out == []
    decisions = FilterDecisionsRepo(conn).list_by_run("r1")
    assert decisions[0]["reason_code"] == "year_too_old"


def test_rule_filter_rejects_missing_abstract(conn):
    spec = RuleFilterSpec(require_year_after=None, require_abstract=True)
    p = _p(title="t", abstract=None, published_date="2024-01-01")
    out = apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    assert out == []
    decisions = FilterDecisionsRepo(conn).list_by_run("r1")
    assert decisions[0]["reason_code"] == "missing_abstract"


def test_rule_filter_blacklist_keyword(conn):
    spec = RuleFilterSpec(require_year_after=None, require_abstract=False, blacklist_keywords=["review article only"])
    p = _p(title="t", abstract="this is review article only no method", published_date="2024-01-01")
    out = apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    assert out == []
    decisions = FilterDecisionsRepo(conn).list_by_run("r1")
    assert decisions[0]["reason_code"] == "blacklist_keyword"


def test_rule_filter_logs_pass_too(conn):
    spec = RuleFilterSpec()
    p = _p(title="t", published_date="2024-01-01")
    apply_rule_filter([p], spec=spec, conn=conn, run_id="r1", paper_ids=[1])
    decisions = FilterDecisionsRepo(conn).list_by_run("r1")
    assert any(d["decision"] == "pass" for d in decisions)
