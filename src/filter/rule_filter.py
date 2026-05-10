"""Rule-based filter applied before LLM screening (which exists from MVP2)."""

from __future__ import annotations

import sqlite3

from src.config import RuleFilterSpec
from src.models.paper import PaperCandidate
from src.storage.repositories import FilterDecisionsRepo


def _year(date: str | None) -> int | None:
    """Extract year from a date string, returning None if unparseable."""
    if not date or len(date) < 4:
        return None
    try:
        return int(date[:4])
    except ValueError:
        return None


def _check(p: PaperCandidate, spec: RuleFilterSpec) -> tuple[str, str | None, str | None]:
    """Inspect one paper against the spec; return (decision, reason_code, reason_text)."""
    if spec.require_year_after is not None:
        y = _year(p.published_date)
        if y is None or y < spec.require_year_after:
            return (
                "reject",
                "year_too_old",
                f"published_date={p.published_date} < {spec.require_year_after}",
            )

    if spec.require_abstract and not (p.abstract and p.abstract.strip()):
        return ("reject", "missing_abstract", "abstract is empty or missing")

    if spec.blacklist_keywords:
        haystack = (p.title + " " + (p.abstract or "")).lower()
        for kw in spec.blacklist_keywords:
            if kw.lower() in haystack:
                return ("reject", "blacklist_keyword", f"matched: {kw}")

    return ("pass", None, None)


def apply_rule_filter(
    papers: list[PaperCandidate],
    spec: RuleFilterSpec,
    conn: sqlite3.Connection,
    run_id: str,
    paper_ids: list[int | None] | None = None,
) -> list[PaperCandidate]:
    """Apply spec; log every decision to filter_decisions; return only papers that passed."""
    repo = FilterDecisionsRepo(conn)
    if paper_ids is None:
        paper_ids = [None] * len(papers)
    out: list[PaperCandidate] = []
    for p, pid in zip(papers, paper_ids, strict=True):
        decision, code, text = _check(p, spec)
        repo.log(run_id=run_id, paper_id=pid, decision=decision, reason_code=code, reason_text=text)
        if decision == "pass":
            out.append(p)
    return out
