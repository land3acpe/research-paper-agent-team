"""Paper field normalization.

Responsibilities:
- Lowercase DOI, strip URL prefix
- Compute normalized_title and title_hash
- Trim author whitespace
- Idempotent
"""
from __future__ import annotations

from src.models.paper import PaperCandidate
from src.normalize.title import normalize_title
from src.utils.hashing import title_hash as _title_hash


def _normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    s = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s


def normalize_paper(p: PaperCandidate) -> PaperCandidate:
    return p.model_copy(update={
        "doi": _normalize_doi(p.doi),
        "normalized_title": normalize_title(p.title),
        "title_hash": _title_hash(p.title),
        "authors": [a.strip() for a in p.authors if a and a.strip()],
    })
