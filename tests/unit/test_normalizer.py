from src.models.paper import PaperCandidate
from src.normalize.normalizer import normalize_paper


def test_normalize_paper_fills_title_hash_and_normalized():
    p = PaperCandidate(source="crossref", title="Dual Three-Phase PMSM!")
    out = normalize_paper(p)
    assert out.normalized_title == "dual three-phase pmsm"
    assert out.title_hash is not None
    assert len(out.title_hash) == 16


def test_normalize_paper_lowercase_doi():
    p = PaperCandidate(source="crossref", title="x", doi="10.1109/TIE.2024.123ABC")
    out = normalize_paper(p)
    assert out.doi == "10.1109/tie.2024.123abc"


def test_normalize_paper_strips_doi_url_prefix():
    p = PaperCandidate(source="crossref", title="x", doi="https://doi.org/10.1/abc")
    out = normalize_paper(p)
    assert out.doi == "10.1/abc"


def test_normalize_paper_strips_authors():
    p = PaperCandidate(source="crossref", title="x", authors=[" A. Author ", "  B. Author"])
    out = normalize_paper(p)
    assert out.authors == ["A. Author", "B. Author"]


def test_normalize_paper_idempotent():
    p = PaperCandidate(source="crossref", title="X")
    once = normalize_paper(p)
    twice = normalize_paper(once)
    assert once == twice
