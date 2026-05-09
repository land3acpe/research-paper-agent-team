import json

from src.models.paper import PaperCandidate
from src.models.run import RunSummary, SourceResult
from src.reports.digest_writer import write_candidates_report, write_run_summary_json


def _p(title: str, **kw) -> PaperCandidate:
    return PaperCandidate(source="crossref", title=title, **kw)


def test_write_candidates_md(tmp_path):
    out = tmp_path / "candidates.md"
    papers = [
        _p("Harmonic suppression", doi="10.1/a", venue="TIE", published_date="2024-03-15", abstract="x"),
        _p("VSD control", doi="10.2/b", venue="TPEL", published_date="2024-05-01"),
    ]
    write_candidates_report(papers, output=out, run_id="r1")
    text = out.read_text(encoding="utf-8")
    assert "# 论文查新候选清单" in text
    assert "r1" in text
    assert "Harmonic suppression" in text
    assert "10.1/a" in text


def test_write_candidates_md_empty(tmp_path):
    out = tmp_path / "candidates.md"
    write_candidates_report([], output=out, run_id="r1")
    text = out.read_text(encoding="utf-8")
    assert "本轮未发现候选论文" in text


def test_write_run_summary_json(tmp_path):
    out = tmp_path / "summary.json"
    s = RunSummary(
        run_id="r1", started_at="2026-05-10T00:00:00+00:00", status="success",
        sources=[SourceResult(source="crossref", query="x", raw_count=10, normalized_count=8)],
        raw_count=10, normalized_count=8, deduped_count=7, filtered_count=5,
    )
    write_run_summary_json(s, output=out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["run_id"] == "r1"
    assert data["sources"][0]["source"] == "crossref"
