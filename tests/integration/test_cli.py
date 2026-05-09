"""Integration tests for the typer CLI entrypoint."""

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from src.fetchers.base import FetchResult
from src.main import app

runner = CliRunner()


def test_cli_help() -> None:
    """--help should list the MVP1 subcommands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "db-init" in result.stdout
    assert "discover" in result.stdout
    assert "run" in result.stdout


def test_cli_db_init(tmp_path: Path) -> None:
    """db-init should create the SQLite database file."""
    db = tmp_path / "papers.db"
    result = runner.invoke(app, ["db-init", "--db-path", str(db)])
    assert result.exit_code == 0
    assert db.exists()


def test_cli_discover_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """discover --dry-run should yield a successful run without DB side effects."""
    from src.fetchers import arxiv as ax
    from src.fetchers import crossref as cr

    def stub(self: Any, query: str, start: Any, end: Any, max_results: int) -> FetchResult:
        return FetchResult(
            source=self.source_name,
            query=query,
            raw_count=0,
            normalized_count=0,
        )

    monkeypatch.setattr(cr.CrossrefFetcher, "fetch", stub)
    monkeypatch.setattr(ax.ArxivFetcher, "fetch", stub)

    cfg = tmp_path / "configs"
    cfg.mkdir()
    (cfg / "schedule.yaml").write_text(
        "schedule:\n  enabled: false\n  mode: weekly\n  timezone: UTC\n"
        "window:\n  daily_days: 3\n  weekly_days: 14\n  monthly_days: 45\n"
        "limits:\n  max_candidates_per_source: 10\n  max_total_candidates: 30\n  max_runtime_minutes: 5\n",
        encoding="utf-8",
    )
    (cfg / "sources.yaml").write_text(
        "sources:\n"
        "  crossref:\n    enabled: true\n    queries: [{name: q1, query: x}]\n    max_results: 10\n"
        "  arxiv:\n    enabled: true\n    categories: [eess.SY]\n    queries: [{name: q1, query: x}]\n    max_results: 10\n",
        encoding="utf-8",
    )
    pdir = cfg / "profiles" / "dtp-pmsm"
    pdir.mkdir(parents=True)
    (pdir / "research_profile.yaml").write_text(
        "research_profile:\n  name: x\n  slug: dtp-pmsm\n  field: f\n"
        "  core_topics: []\n  reject_topics: []\n"
        "  rule_filter: {require_year_after: null, require_abstract: false, blacklist_keywords: []}\n",
        encoding="utf-8",
    )

    data = tmp_path / "data"
    db = tmp_path / "papers.db"
    result = runner.invoke(
        app,
        [
            "--config-dir", str(cfg), "--profile", "dtp-pmsm",
            "discover", "--db-path", str(db), "--data-dir", str(data),
            "--days", "14", "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.stdout
    # dry-run must not write to the database.
    assert not db.exists() or db.stat().st_size == 0
