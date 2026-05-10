"""Hashing utilities for paper deduplication."""

from __future__ import annotations

import hashlib

from src.normalize.title import normalize_title


def title_hash(title: str) -> str:
    """Stable hash over normalized title. First 16 hex of sha256."""
    norm = normalize_title(title)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
