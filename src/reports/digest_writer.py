"""Report rendering for MVP1 (candidates + run summary).

Future MVPs will extend this module with digest generation; for now it only
emits the deterministic Markdown/JSON outputs of MVP1.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models.paper import PaperCandidate
from src.models.run import RunSummary

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["md", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def write_candidates_report(
    papers: list[PaperCandidate],
    output: Path,
    run_id: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmpl = _env.get_template("candidates.md.j2")
    rendered = tmpl.render(
        papers=papers,
        run_id=run_id,
        generated_at=datetime.now(UTC).isoformat(),
    )
    output.write_text(rendered, encoding="utf-8")


def write_run_summary_md(summary: RunSummary, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmpl = _env.get_template("run_summary.md.j2")
    output.write_text(tmpl.render(summary=summary), encoding="utf-8")


def write_run_summary_json(summary: RunSummary, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
