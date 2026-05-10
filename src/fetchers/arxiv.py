"""arXiv API fetcher.

Endpoint: http://export.arxiv.org/api/query
Returns Atom XML; parsed via feedparser.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import feedparser
import structlog

from src.fetchers._http import make_client
from src.fetchers.base import FetcherBase, FetchResult
from src.models.paper import PaperCandidate

logger = structlog.get_logger(__name__)

_BASE_URL = "http://export.arxiv.org/api/query"
_VERSION_SUFFIX = re.compile(r"v\d+$")


def _strip_version(arxiv_id: str) -> str:
    """Convert '2503.12345v1' or 'http://arxiv.org/abs/2503.12345v1' -> '2503.12345'."""
    short = arxiv_id.rsplit("/", 1)[-1]
    return _VERSION_SUFFIX.sub("", short)


class ArxivFetcher(FetcherBase):
    source_name = "arxiv"

    def __init__(self, base_url: str = _BASE_URL) -> None:
        self.base_url = base_url

    def parse_response(self, payload: str) -> list[PaperCandidate]:
        feed = feedparser.parse(payload)
        out: list[PaperCandidate] = []
        for entry in feed.entries:
            try:
                arxiv_id = _strip_version(entry.id)
                published = entry.get("published", "")[:10] or None

                authors = [
                    a.name.strip()
                    for a in entry.get("authors", [])
                    if getattr(a, "name", "").strip()
                ]

                pdf_url = None
                html_url = None
                for link in entry.get("links", []):
                    if link.get("type") == "application/pdf":
                        pdf_url = link.get("href")
                    elif link.get("rel") == "alternate":
                        html_url = link.get("href")

                title = (entry.get("title") or "").strip()
                if not title:
                    continue

                out.append(PaperCandidate(
                    source=self.source_name,
                    source_id=arxiv_id,
                    doi=f"10.48550/arXiv.{arxiv_id}",
                    title=title,
                    authors=authors,
                    venue="arXiv",
                    published_date=published,
                    indexed_date=entry.get("updated", "")[:19] or None,
                    abstract=(entry.get("summary") or "").strip() or None,
                    url=html_url or entry.id,
                    pdf_url=pdf_url,
                    raw={k: v for k, v in entry.items() if isinstance(v, (str, int, float, bool, list, dict))},
                ))
            except Exception as e:
                logger.warning("arxiv_parse_entry_failed", error=str(e), entry_id=entry.get("id"))
        return out

    def fetch(
        self,
        query: str,
        start: datetime,
        end: datetime,
        max_results: int,
    ) -> FetchResult:
        result = FetchResult(source=self.source_name, query=query)
        params: dict[str, Any] = {
            "search_query": query,
            "start": 0,
            "max_results": min(max_results, 2000),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            with make_client() as client:
                resp = client.get(self.base_url, params=params)
                resp.raise_for_status()
                payload = resp.text
                result.raw_payload = payload
                feed = feedparser.parse(payload)
                result.raw_count = len(feed.entries)
                result.candidates = self.parse_response(payload)
                # Filter by published date
                result.candidates = [
                    p for p in result.candidates
                    if p.published_date is None
                    or (start.strftime("%Y-%m-%d") <= p.published_date <= end.strftime("%Y-%m-%d"))
                ]
                result.normalized_count = len(result.candidates)
        except Exception as e:
            logger.error("arxiv_fetch_failed", error=str(e), query=query)
            result.errors.append(f"arxiv: {type(e).__name__}: {e}")
        return result
