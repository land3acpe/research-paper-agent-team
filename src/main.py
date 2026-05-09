"""CLI entrypoint (typer).

MVP1 commands: db-init / discover / run / report

Global options applied via Typer callback for context.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from src.config import load_config
from src.logging_config import configure_logging
from src.orchestrator import run_mvp1_pipeline
from src.storage.db import apply_migrations, open_db

app = typer.Typer(no_args_is_help=True, help="research-paper-agent-team CLI (MVP1)")

_ConfigDir = Annotated[Path, typer.Option("--config-dir", help="Path to configs/ directory")]
_Profile = Annotated[str, typer.Option("--profile", help="Profile slug under configs/profiles/")]
_DryRun = Annotated[bool, typer.Option("--dry-run", help="No DB writes, no external side effects")]
_LogLevel = Annotated[str, typer.Option("--log-level")]
_DbPath = Annotated[Path, typer.Option("--db-path", help="SQLite DB path")]
_DataDir = Annotated[Path, typer.Option("--data-dir", help="data/ root for raw/normalized/reports/logs")]


@app.callback()
def _global_options(
    ctx: typer.Context,
    config_dir: _ConfigDir = Path("configs"),
    profile: _Profile = "dtp-pmsm",
    log_level: _LogLevel = "info",
) -> None:
    configure_logging(log_level=log_level)
    ctx.obj = {"config_dir": config_dir, "profile": profile, "log_level": log_level}


@app.command("db-init")
def db_init_cmd(
    db_path: _DbPath = Path("data/papers.db"),
) -> None:
    """Initialize SQLite schema."""
    conn = open_db(db_path)
    apply_migrations(conn)
    conn.close()
    typer.echo(f"DB initialized at {db_path}")


@app.command("discover")
def discover_cmd(
    ctx: typer.Context,
    db_path: _DbPath = Path("data/papers.db"),
    data_dir: _DataDir = Path("data"),
    days: Annotated[int, typer.Option("--days")] = 14,
    schedule_mode: Annotated[str, typer.Option("--mode")] = "manual",
    dry_run: _DryRun = False,
) -> None:
    """Discover new papers (fetch -> normalize -> dedupe -> rule_filter -> report)."""
    config = load_config(config_dir=ctx.obj["config_dir"], profile=ctx.obj["profile"])
    summary = run_mvp1_pipeline(
        config=config,
        db_path=db_path,
        data_dir=data_dir,
        schedule_mode=schedule_mode,
        dry_run=dry_run,
        days=days,
    )
    typer.echo(f"run_id: {summary.run_id}")
    typer.echo(f"status: {summary.status}")
    typer.echo(
        f"raw={summary.raw_count} normalized={summary.normalized_count} "
        f"deduped={summary.deduped_count} filtered={summary.filtered_count}"
    )
    typer.echo(f"report: {summary.report_path}")


@app.command("run")
def run_cmd(
    ctx: typer.Context,
    db_path: _DbPath = Path("data/papers.db"),
    data_dir: _DataDir = Path("data"),
    days: Annotated[int, typer.Option("--days")] = 14,
    schedule_mode: Annotated[str, typer.Option("--mode")] = "manual",
    dry_run: _DryRun = False,
) -> None:
    """End-to-end run. In MVP1 equivalent to `discover`."""
    return discover_cmd(
        ctx=ctx,
        db_path=db_path,
        data_dir=data_dir,
        days=days,
        schedule_mode=schedule_mode,
        dry_run=dry_run,
    )


@app.command("report")
def report_cmd(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Option("--run-id", help="Run ID to re-render report for")],
    db_path: _DbPath = Path("data/papers.db"),
    data_dir: _DataDir = Path("data"),
) -> None:
    """Re-render report for an existing run_id from SQLite state."""
    import json as _json

    from src.models.paper import PaperCandidate
    from src.reports.digest_writer import write_candidates_report
    from src.storage.repositories import PapersRepo

    conn = open_db(db_path)
    apply_migrations(conn)
    papers_rows = PapersRepo(conn).list_by_run(run_id)
    conn.close()

    papers = [
        PaperCandidate(
            source=row["source"],
            source_id=row["source_id"],
            doi=row["doi"],
            title=row["title"],
            normalized_title=row["normalized_title"],
            title_hash=row["title_hash"],
            authors=_json.loads(row["authors_json"] or "[]"),
            venue=row["venue"],
            published_date=row["published_date"],
            abstract=row["abstract"],
            url=row["url"],
            pdf_url=row["pdf_url"],
        )
        for row in papers_rows
    ]
    output = data_dir / "reports" / run_id / "candidates.md"
    write_candidates_report(papers, output=output, run_id=run_id)
    typer.echo(f"Re-rendered: {output}")


if __name__ == "__main__":
    app()
