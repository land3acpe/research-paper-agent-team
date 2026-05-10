import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.fetchers.crossref import CrossrefFetcher

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "crossref"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_crossref_parse_response():
    fetcher = CrossrefFetcher(mailto="test@example.com")
    candidates = fetcher.parse_response(_load("search_dtp_pmsm.json"))
    assert len(candidates) == 2
    p1 = candidates[0]
    assert p1.source == "crossref"
    assert p1.doi == "10.1109/TIE.2024.001"
    assert p1.title.startswith("Harmonic current suppression")
    assert p1.authors == ["A. Author", "B. Author"]
    assert p1.venue == "IEEE Transactions on Industrial Electronics"
    assert p1.published_date == "2024-03-15"
    assert "harmonic current suppression" in (p1.abstract or "").lower()
    # JATS tags should be stripped
    assert "<jats:p>" not in (p1.abstract or "")


def test_crossref_parse_empty():
    fetcher = CrossrefFetcher()
    candidates = fetcher.parse_response(_load("empty_response.json"))
    assert candidates == []


def test_crossref_partial_date():
    payload = {
        "status": "ok",
        "message": {
            "items": [{
                "DOI": "10.1/x",
                "title": ["x"],
                "issued": {"date-parts": [[2024]]},
                "container-title": ["J"],
            }]
        }
    }
    candidates = CrossrefFetcher().parse_response(payload)
    assert candidates[0].published_date == "2024-01-01"


_CROSSREF_URL_RE = re.compile(r"https://api\.crossref\.org/works")

def test_crossref_fetch_uses_mock_http(httpx_mock):
    httpx_mock.add_response(
        url=_CROSSREF_URL_RE,
        json=_load("search_dtp_pmsm.json"),
    )
    fetcher = CrossrefFetcher(mailto="test@example.com")
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 12, 31, tzinfo=timezone.utc)
    result = fetcher.fetch(query="dual three-phase PMSM", start=start, end=end, max_results=10)
    assert result.raw_count == 2
    assert result.normalized_count == 2
    assert len(result.candidates) == 2


def test_crossref_fetch_handles_http_error(httpx_mock):
    httpx_mock.add_response(
        url=_CROSSREF_URL_RE,
        status_code=503,
    )
    fetcher = CrossrefFetcher()
    result = fetcher.fetch(
        query="x",
        start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end=datetime(2024, 12, 31, tzinfo=timezone.utc),
        max_results=10,
    )
    assert len(result.errors) > 0
    assert result.candidates == []
