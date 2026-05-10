import pytest

from src.config import (
    AppConfig,
    ArxivSource,
    CrossrefSource,
    LimitsSection,
    QuerySpec,
    ResearchProfile,
    RuleFilterSpec,
    ScheduleSection,
    SourcesConfig,
    WindowSection,
)
from src.fetchers.base import FetchResult
from src.models.paper import PaperCandidate
from src.orchestrator import run_mvp1_pipeline
from src.storage.db import apply_migrations, open_db
from src.storage.repositories import FilterDecisionsRepo, PapersRepo, RunsRepo


def _make_config() -> AppConfig:
    return AppConfig(
        schedule=ScheduleSection(enabled=False, mode="weekly", timezone="UTC"),
        window=WindowSection(daily_days=3, weekly_days=14, monthly_days=45),
        limits=LimitsSection(
            max_candidates_per_source=10, max_total_candidates=30, max_runtime_minutes=5
        ),
        sources=SourcesConfig(
            crossref=CrossrefSource(
                enabled=True, queries=[QuerySpec(name="q1", query="x")], max_results=10
            ),
            arxiv=ArxivSource(
                enabled=True, queries=[QuerySpec(name="q1", query="x")], max_results=10
            ),
        ),
        profile=ResearchProfile(
            name="x",
            slug="dtp-pmsm",
            field="f",
            rule_filter=RuleFilterSpec(
                require_year_after=2018, require_abstract=False, blacklist_keywords=[]
            ),
        ),
    )


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "papers.db"


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


def _stub_fetchers(monkeypatch):
    """Replace real fetchers with stubs returning canned PaperCandidate lists."""
    from src.fetchers import arxiv as ax
    from src.fetchers import crossref as cr

    def crossref_fetch(self, query, start, end, max_results):
        return FetchResult(
            source="crossref",
            query=query,
            raw_count=2,
            normalized_count=2,
            candidates=[
                PaperCandidate(
                    source="crossref",
                    title="Crossref paper A",
                    doi="10.1/a",
                    abstract="x",
                    published_date="2024-03-15",
                ),
                PaperCandidate(
                    source="crossref",
                    title="Crossref paper B",
                    doi="10.1/b",
                    abstract="x",
                    published_date="2024-04-15",
                ),
            ],
        )

    def arxiv_fetch(self, query, start, end, max_results):
        return FetchResult(
            source="arxiv",
            query=query,
            raw_count=1,
            normalized_count=1,
            candidates=[
                PaperCandidate(
                    source="arxiv",
                    source_id="2503.99999",
                    title="Arxiv paper A",
                    doi="10.48550/arXiv.2503.99999",
                    abstract="x",
                    published_date="2024-05-15",
                ),
            ],
        )

    monkeypatch.setattr(cr.CrossrefFetcher, "fetch", crossref_fetch)
    monkeypatch.setattr(ax.ArxivFetcher, "fetch", arxiv_fetch)


def test_pipeline_e2e(monkeypatch, db_path, data_dir):
    _stub_fetchers(monkeypatch)
    config = _make_config()
    summary = run_mvp1_pipeline(
        config=config,
        db_path=db_path,
        data_dir=data_dir,
        schedule_mode="weekly",
        dry_run=False,
    )
    assert summary.status in ("success", "partial")
    assert summary.raw_count == 3
    assert summary.normalized_count == 3
    assert summary.deduped_count >= 1

    conn = open_db(db_path)
    apply_migrations(conn)
    assert RunsRepo(conn).get_by_run_id(summary.run_id) is not None
    assert len(PapersRepo(conn).list_by_run(summary.run_id)) >= 1
    assert len(FilterDecisionsRepo(conn).list_by_run(summary.run_id)) >= 1
    conn.close()

    # Report files exist
    assert (data_dir / "reports" / summary.run_id / "candidates.md").exists()
    assert (data_dir / "reports" / summary.run_id / "summary.json").exists()


def test_pipeline_dry_run_does_not_write_db(monkeypatch, db_path, data_dir):
    _stub_fetchers(monkeypatch)
    config = _make_config()
    summary = run_mvp1_pipeline(
        config=config,
        db_path=db_path,
        data_dir=data_dir,
        schedule_mode="manual",
        dry_run=True,
    )
    # DB file may or may not exist; if it does, it must have no papers
    if db_path.exists():
        conn = open_db(db_path)
        apply_migrations(conn)
        assert RunsRepo(conn).get_by_run_id(summary.run_id) is None
        conn.close()
    # Reports go under _dryrun/
    assert (data_dir / "reports" / "_dryrun" / summary.run_id / "candidates.md").exists()


def test_pipeline_partial_when_one_source_fails(monkeypatch, db_path, data_dir):
    from src.fetchers import arxiv as ax
    from src.fetchers import crossref as cr

    def crossref_fetch_fail(self, query, start, end, max_results):
        return FetchResult(
            source="crossref",
            query=query,
            raw_count=0,
            normalized_count=0,
            candidates=[],
            errors=["crossref: 503"],
        )

    def arxiv_fetch_ok(self, query, start, end, max_results):
        return FetchResult(
            source="arxiv",
            query=query,
            raw_count=1,
            normalized_count=1,
            candidates=[
                PaperCandidate(
                    source="arxiv",
                    source_id="x",
                    title="ok",
                    abstract="a",
                    published_date="2024-01-01",
                )
            ],
        )

    monkeypatch.setattr(cr.CrossrefFetcher, "fetch", crossref_fetch_fail)
    monkeypatch.setattr(ax.ArxivFetcher, "fetch", arxiv_fetch_ok)

    config = _make_config()
    summary = run_mvp1_pipeline(
        config=config,
        db_path=db_path,
        data_dir=data_dir,
        schedule_mode="manual",
        dry_run=False,
    )
    assert summary.status == "partial"
