"""Hard deduplication based on stable IDs (DOI / arXiv ID / source-specific ID)."""
from __future__ import annotations

from src.models.paper import PaperCandidate

HardKey = tuple[str, str]


def find_hard_duplicate_key(p: PaperCandidate) -> HardKey | None:
    """Return a stable identity key for a paper, or None if no hard ID is available."""
    if p.doi:
        return ("doi", p.doi.lower())
    if p.source and p.source_id:
        return ("source_id", f"{p.source}:{p.source_id}")
    return None


def dedupe_hard(
    papers: list[PaperCandidate],
) -> tuple[list[PaperCandidate], list[tuple[PaperCandidate, PaperCandidate, str]]]:
    """Return (unique_list, dup_pairs).

    - First occurrence wins.
    - Papers without a hard key pass through unchanged.
    - dup_pairs are (kept, dropped, match_type) for logging/audit.
    """
    seen: dict[HardKey, PaperCandidate] = {}
    unique: list[PaperCandidate] = []
    dups: list[tuple[PaperCandidate, PaperCandidate, str]] = []

    for p in papers:
        key = find_hard_duplicate_key(p)
        if key is None:
            unique.append(p)
            continue
        if key in seen:
            dups.append((seen[key], p, key[0]))
        else:
            seen[key] = p
            unique.append(p)
    return unique, dups
