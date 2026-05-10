from src.dedupe.hard import dedupe_hard, find_hard_duplicate_key
from src.models.paper import PaperCandidate


def test_find_hard_key_doi():
    p = PaperCandidate(source="crossref", title="x", doi="10.1/abc")
    assert find_hard_duplicate_key(p) == ("doi", "10.1/abc")


def test_find_hard_key_arxiv_source_id():
    p = PaperCandidate(source="arxiv", title="x", source_id="2503.12345")
    assert find_hard_duplicate_key(p) == ("source_id", "arxiv:2503.12345")


def test_find_hard_key_none():
    p = PaperCandidate(source="rss", title="x")
    assert find_hard_duplicate_key(p) is None


def test_dedupe_hard_removes_doi_duplicates():
    p1 = PaperCandidate(source="crossref", title="x", doi="10.1/abc")
    p2 = PaperCandidate(source="arxiv", title="y", doi="10.1/abc")  # 同 DOI
    p3 = PaperCandidate(source="crossref", title="z", doi="10.2/xyz")
    unique, dup_pairs = dedupe_hard([p1, p2, p3])
    assert len(unique) == 2
    assert len(dup_pairs) == 1


def test_dedupe_hard_keeps_first_occurrence():
    p1 = PaperCandidate(source="crossref", title="first", doi="10.1/abc")
    p2 = PaperCandidate(source="arxiv", title="second", doi="10.1/abc")
    unique, _ = dedupe_hard([p1, p2])
    assert unique[0].title == "first"
