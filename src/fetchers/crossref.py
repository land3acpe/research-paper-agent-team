"""Crossref REST API fetcher.

Endpoint: https://api.crossref.org/works
Docs: https://api.crossref.org/swagger-ui/index.html
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import structlog

from src.fetchers._http import make_client
from src.fetchers.base import FetcherBase, FetchResult
from src.models.paper import PaperCandidate

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.crossref.org/works"
_JATS_TAG = re.compile(r"<[^>]+>")


def _strip_jats(text: str) -> str:
    return _JATS_TAG.sub("", text).strip()


def _format_date_parts(date_parts: list[int] | None) -> str | None:
    if not date_parts:
        return None
    parts = list(date_parts) + [1, 1]  # pad to YMD
    y, m, d = parts[0], parts[1], parts[2]
    return f"{y:04d}-{m:02d}-{d:02d}"


def _author_name(a: dict[str, Any]) -> str:
    given = a.get("given", "").strip()
    family = a.get("family", "").strip()
    return f"{given} {family}".strip()


class CrossrefFetcher(FetcherBase):
    source_name = "crossref"

    def __init__(self, mailto: str | None = None, base_url: str = _BASE_URL) -> None:
        self.mailto = mailto
        self.base_url = base_url

    def parse_response(self, payload: dict[str, Any]) -> list[PaperCandidate]:
        items = (payload.get("message") or {}).get("items") or []
        out: list[PaperCandidate] = []
        for it in items:
            try:
                title_list = it.get("title") or []
                title = title_list[0] if title_list else ""
                if not title:
                    continue
                venue_list = it.get("container-title") or []
                venue = venue_list[0] if venue_list else None

                date_parts = (it.get("issued") or {}).get("date-parts") or [[]]
                published = _format_date_parts(date_parts[0]) if date_parts else None
                indexed_dt = (it.get("created") or {}).get("date-time")

                authors = [_author_name(a) for a in (it.get("author") or [])]
                abstract_raw = it.get("abstract")
                abstract = _strip_jats(abstract_raw) if abstract_raw else None

                out.append(PaperCandidate(
                    source=self.source_name,
                    source_id=it.get("DOI"),
                    doi=it.get("DOI"),
                    title=title,
                    authors=authors,
                    venue=venue,
                    published_date=published,
                    indexed_date=indexed_dt,
                    abstract=abstract,
                    url=it.get("URL"),
                    raw=it,
                ))
            except Exception as e:
                logger.warning("crossref_parse_item_failed", error=str(e), item_doi=it.get("DOI"))
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
            "query.bibliographic": query,
            "from-pub-date": start.strftime("%Y-%m-%d"),
            "until-pub-date": end.strftime("%Y-%m-%d"),
            "rows": min(max_results, 1000),
            "sort": "issued",
            "order": "desc",
        }
        if self.mailto:
            params["mailto"] = self.mailto

        try:
            with make_client() as client:
                resp = client.get(self.base_url, params=params)
                resp.raise_for_status()
                payload = resp.json()
                result.raw_payload = payload
                items = (payload.get("message") or {}).get("items") or []
                result.raw_count = len(items)
                result.candidates = self.parse_response(payload)
                result.normalized_count = len(result.candidates)
        except Exception as e:
            logger.error("crossref_fetch_failed", error=str(e), query=query)
            result.errors.append(f"crossref: {type(e).__name__}: {e}")
        return result
