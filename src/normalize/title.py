"""Title normalization for hashing and fuzzy matching."""
from __future__ import annotations

import re
import unicodedata

_HTML_TAG = re.compile(r"<[^>]+>")
_PUNCT = re.compile(r"[^\w\s-]")
_WS = re.compile(r"\s+")
_DASH_WORD_BREAK = re.compile(r"\s+-\s+")
_UNICODE_DASHES = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2212": "-"})


def normalize_title(title: str) -> str:
    """Lowercase, strip HTML, collapse whitespace, unify dashes, strip punctuation."""
    if not title:
        return ""
    s = _HTML_TAG.sub("", title)
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_UNICODE_DASHES)
    s = s.lower()
    s = _DASH_WORD_BREAK.sub(" ", s)
    s = _PUNCT.sub("", s)
    s = _WS.sub(" ", s).strip()
    return s
