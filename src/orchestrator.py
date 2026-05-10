"""MVP1 pipeline orchestrator (deterministic, no LLM).

Pipeline:
  fetchers (Crossref + arXiv) -> normalize -> dedupe -> rule_filter -> SQLite + report
"""
from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import structlog

from src.config import AppConfig
from src.dedupe.deduplicator import deduplicate
from src.fetchers.arxiv import ArxivFetcher
from src.fetchers.crossref import CrossrefFetcher
from src.filter.rule_filter import apply_rule_filter
from src.models.paper import PaperCandidate
from src.models.run import RunSummary, SourceResult
from src.normalize.normalizer import normalize_paper
from src.reports.digest_writer import (
    write_candidates_report,
    write_run_summary_json,
    write_run_summary_md,
)
from src.storage.db import apply_migrations, open_db
from src.storage.repositories import PapersRepo, RunsRepo
from src.utils.runid import generate_run_id
from src.utils.time import compute_window

logger = structlog.get_logger(__name__)


def _report_dir(data_dir: Path, run_id: str, *, dry_run: bool) -> Path:
    """Resolve the reports output directory, creating it as a side effect."""
    if dry_run:
        base = data_dir / "reports" / "_dryrun" / run_id
    else:
        base = data_dir / "reports" / run_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def _run_fetchers(
    config: AppConfig,
    window_start: datetime,
    window_end: datetime,
) -> tuple[list[PaperCandidate], list[SourceResult]]:
    """Execute all enabled fetchers, collecting candidates and per-source results."""
    all_candidates: list[PaperCandidate] = []
    source_results: list[SourceResult] = []

    if config.sources.crossref.enabled:
        mailto = os.environ.get(config.sources.crossref.mailto_env)
        cr = CrossrefFetcher(mailto=mailto)
        for q in config.sources.crossref.queries:
            res = cr.fetch(
                query=q.query,
                start=window_start,
                end=window_end,
                max_results=config.sources.crossref.max_results,
            )
            source_results.append(SourceResult(
                source="crossref",
                query=q.query,
                raw_count=res.raw_count,
                normalized_count=res.normalized_count,
                errors=res.errors,
            ))
            all_candidates.extend(res.candidates)

    if config.sources.arxiv.enabled:
        ax = ArxivFetcher()
        for q in config.sources.arxiv.queries:
            res = ax.fetch(
                query=q.query,
                start=window_start,
                end=window_end,
                max_results=config.sources.arxiv.max_results,
            )
            source_results.append(SourceResult(
                source="arxiv",
                query=q.query,
                raw_count=res.raw_count,
                normalized_count=res.normalized_count,
                errors=res.errors,
            ))
            all_candidates.extend(res.candidates)

    return all_candidates, source_results


def _resolve_paper_id(repo: PapersRepo, p: PaperCandidate, run_id: str) -> int | None:
    """Look up a paper in the DB and return its id, inserting if not found."""
    existing = (
        (p.doi and repo.get_by_doi(p.doi))
        or (p.source_id and repo.get_by_source_id(p.source, p.source_id))
        or (p.title_hash and repo.get_by_title_hash(p.title_hash))
    )
    if existing:
        return existing["id"]
    return repo.insert(p, run_id=run_id)


def run_mvp1_pipeline(
    config: AppConfig,
    db_path: Path,
    data_dir: Path,
    schedule_mode: str = "manual",
    dry_run: bool = False,
    days: int | None = None,
) -> RunSummary:
    """Execute the MVP1 pipeline: fetch -> normalize -> dedupe -> filter -> report.

    Returns a RunSummary describing counts and per-source outcomes.
    """
    run_id = generate_run_id(profile_slug=config.profile.slug, schedule_mode=schedule_mode)
    started = datetime.now(UTC).isoformat()

    if days is None:
        days = {
            "daily": config.window.daily_days,
            "weekly": config.window.weekly_days,
            "monthly": config.window.monthly_days,
        }.get(schedule_mode, config.window.weekly_days)
    window_start, window_end = compute_window(days=days)

    summary = RunSummary(
        run_id=run_id,
        started_at=started,
        status="running",
        dry_run=dry_run,
    )

    log = logger.bind(run_id=run_id, dry_run=dry_run)
    log.info("pipeline_start", schedule_mode=schedule_mode, days=days)

    # ---- 1. Fetch ----
    candidates, source_results = _run_fetchers(config, window_start, window_end)
    summary.sources = source_results
    summary.raw_count = sum(s.raw_count for s in source_results)

    # ---- 2. Normalize ----
    candidates = [normalize_paper(p) for p in candidates]
    summary.normalized_count = len(candidates)

    # ---- 3. Deduplicate ----
    if dry_run:
        outcome = deduplicate(candidates, conn=None)
        summary.deduped_count = len(outcome.unique)
        deduped_ids: list[int | None] = [None] * len(outcome.unique)
        conn = None
    else:
        conn = open_db(db_path)
        apply_migrations(conn)
        papers_repo = PapersRepo(conn)

        # Ensure every candidate has a DB row so soft-dedup can reference paper_ids.
        for p in candidates:
            _resolve_paper_id(papers_repo, p, run_id)

        outcome = deduplicate(candidates, conn=conn)
        summary.deduped_count = len(outcome.unique)

        # Resolve deduped subset to DB ids for the filter step.
        deduped_ids = [_resolve_paper_id(papers_repo, p, run_id) for p in outcome.unique]

    # ---- 4. Rule Filter ----
    if dry_run:
        tmp_conn = sqlite3.connect(":memory:")
        try:
            apply_migrations(tmp_conn)
            passed = apply_rule_filter(
                outcome.unique,
                spec=config.profile.rule_filter,
                conn=tmp_conn,
                run_id=run_id,
                paper_ids=deduped_ids,
            )
        finally:
            tmp_conn.close()
    else:
        passed = apply_rule_filter(
            outcome.unique,
            spec=config.profile.rule_filter,
            conn=conn,
            run_id=run_id,
            paper_ids=deduped_ids,
        )

    summary.filtered_count = len(passed)

    # ---- 5. Reports ----
    reports_dir = _report_dir(data_dir, run_id, dry_run=dry_run)
    candidates_path = reports_dir / "candidates.md"
    summary_md_path = reports_dir / "summary.md"
    summary_json_path = reports_dir / "summary.json"

    write_candidates_report(passed, output=candidates_path, run_id=run_id)
    summary.report_path = str(candidates_path)
    summary.ended_at = datetime.now(UTC).isoformat()

    has_source_errors = any(s.errors for s in source_results)
    summary.status = "partial" if has_source_errors else "success"

    write_run_summary_md(summary, output=summary_md_path)
    write_run_summary_json(summary, output=summary_json_path)

    # ---- 6. Persist run row ----
    if not dry_run:
        runs_repo = RunsRepo(conn)
        runs_repo.insert(summary, profile_slug=config.profile.slug, schedule_mode=schedule_mode)
        runs_repo.update_summary(summary)
        conn.close()

    log.info("pipeline_done", status=summary.status, filtered=summary.filtered_count)
    return summary
