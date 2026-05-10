"""Tests for ArxivFetcher."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from src.fetchers.arxiv import ArxivFetcher

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "arxiv"

_ARXIV_URL_RE = re.compile(r"http://export\.arxiv\.org/api/query")


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_arxiv_parse_response():
    payload = _load("search_motor_control.xml")
    candidates = ArxivFetcher().parse_response(payload)
    assert len(candidates) == 2
    p = candidates[0]
    assert p.source == "arxiv"
    assert p.source_id == "2503.12345"  # version stripped
    assert p.title.startswith("Neural network based")
    assert p.authors == ["Alice Author", "Bob Researcher"]
    assert p.published_date == "2025-03-15"
    assert p.url == "http://arxiv.org/abs/2503.12345v1"
    assert p.pdf_url == "http://arxiv.org/pdf/2503.12345v1"
    assert "neural network" in (p.abstract or "").lower()


def test_arxiv_parse_empty():
    payload = _load("empty_response.xml")
    assert ArxivFetcher().parse_response(payload) == []


def test_arxiv_strips_version_suffix():
    payload = _load("search_motor_control.xml")
    candidates = ArxivFetcher().parse_response(payload)
    p = candidates[1]
    assert p.source_id == "2504.99999"  # v2 stripped


def test_arxiv_fetch_with_mock(httpx_mock):
    payload = _load("search_motor_control.xml")
    httpx_mock.add_response(
        url=_ARXIV_URL_RE,
        text=payload,
        headers={"content-type": "application/atom+xml"},
    )
    result = ArxivFetcher().fetch(
        query="motor control",
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 12, 31, tzinfo=UTC),
        max_results=10,
    )
    assert result.raw_count == 2
    assert result.normalized_count == 2


def test_arxiv_fetch_handles_error(httpx_mock):
    httpx_mock.add_response(
        url=_ARXIV_URL_RE,
        status_code=500,
    )
    result = ArxivFetcher().fetch(
        query="x",
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 12, 31, tzinfo=UTC),
        max_results=10,
    )
    assert len(result.errors) > 0
