"""Deduplication orchestrator.

- Hard dedup: auto-merge based on DOI / source_id (in-memory list).
- Soft dedup: emit dedup_candidates rows to SQLite for manual review.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import structlog

from src.dedupe.hard import dedupe_hard
from src.dedupe.soft import find_soft_matches
from src.models.paper import PaperCandidate
from src.storage.repositories import DedupCandidatesRepo, PapersRepo

logger = structlog.get_logger(__name__)


@dataclass
class DedupeOutcome:
    unique: list[PaperCandidate]
    hard_dup_count: int
    soft_match_count: int


def _resolve_db_id(repo: PapersRepo, p: PaperCandidate) -> int | None:
    """Map an in-memory PaperCandidate to its DB row id."""
    if p.doi:
        row = repo.get_by_doi(p.doi)
        if row is not None:
            return row["id"]
    if p.source and p.source_id:
        row = repo.get_by_source_id(p.source, p.source_id)
        if row is not None:
            return row["id"]
    if p.title_hash:
        row = repo.get_by_title_hash(p.title_hash)
        if row is not None:
            return row["id"]
    return None


def _resolve_pair_ids(
    repo: PapersRepo, a: PaperCandidate, b: PaperCandidate
) -> tuple[int, int] | None:
    """Return (id_a, id_b) if both papers can be resolved to distinct DB rows."""
    id_a = _resolve_db_id(repo, a)
    id_b = _resolve_db_id(repo, b)

    if id_a is None or id_b is None:
        return None

    if id_a != id_b:
        return id_a, id_b

    # Same ID resolved — both papers share the same lookup key (e.g. title_hash).
    # Try to find both distinct rows via title_hash listing.
    if a.title_hash:
        all_rows = repo.list_by_title_hash(a.title_hash)
        if len(all_rows) >= 2:
            return all_rows[0]["id"], all_rows[1]["id"]

    return None


def deduplicate(
    papers: list[PaperCandidate],
    conn: sqlite3.Connection | None = None,
    soft_threshold: float = 90.0,
) -> DedupeOutcome:
    unique, hard_dups = dedupe_hard(papers)

    soft_matches = find_soft_matches(unique, threshold=soft_threshold)

    if conn is not None and soft_matches:
        papers_repo = PapersRepo(conn)
        dedup_repo = DedupCandidatesRepo(conn)
        for m in soft_matches:
            a = unique[m.idx_a]
            b = unique[m.idx_b]
            pair = _resolve_pair_ids(papers_repo, a, b)
            if pair is not None:
                id_a, id_b = pair
                dedup_repo.insert(
                    paper_id_a=id_a,
                    paper_id_b=id_b,
                    match_type=m.match_type,
                    similarity=m.similarity,
                )

    logger.info(
        "dedup_done",
        in_count=len(papers),
        unique=len(unique),
        hard_dups=len(hard_dups),
        soft_matches=len(soft_matches),
    )
    return DedupeOutcome(
        unique=unique,
        hard_dup_count=len(hard_dups),
        soft_match_count=len(soft_matches),
    )
