"""Repository layer over SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from src.models.paper import PaperCandidate
from src.models.run import RunSummary


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row(result: sqlite3.Row | None) -> sqlite3.Row | None:
    """Narrow sqlite3.Row | None for mypy — sqlite3.execute is untyped."""
    return result


def _insert_id(cur: sqlite3.Cursor) -> int:
    lastrowid = cur.lastrowid
    assert lastrowid is not None, "INSERT did not return a lastrowid"
    return lastrowid


class PapersRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(
        self, p: PaperCandidate, status: str = "candidate", run_id: str | None = None
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO papers (
                doi, title, normalized_title, title_hash, source, source_id,
                url, pdf_url, authors_json, venue, published_date, indexed_date,
                abstract, keywords_json, status, raw_json, run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p.doi,
                p.title,
                p.normalized_title,
                p.title_hash,
                p.source,
                p.source_id,
                p.url,
                p.pdf_url,
                json.dumps(p.authors),
                p.venue,
                p.published_date,
                p.indexed_date,
                p.abstract,
                json.dumps(p.keywords),
                status,
                json.dumps(p.raw),
                run_id,
                _now(),
                _now(),
            ),
        )
        return _insert_id(cur)

    def get_by_doi(self, doi: str) -> sqlite3.Row | None:
        return _row(self.conn.execute("SELECT * FROM papers WHERE doi = ?", (doi,)).fetchone())

    def get_by_title_hash(self, title_hash: str) -> sqlite3.Row | None:
        return _row(
            self.conn.execute("SELECT * FROM papers WHERE title_hash = ?", (title_hash,)).fetchone()
        )

    def list_by_title_hash(self, title_hash: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM papers WHERE title_hash = ? ORDER BY id", (title_hash,)
            ).fetchall()
        )

    def get_by_source_id(self, source: str, source_id: str) -> sqlite3.Row | None:
        return _row(
            self.conn.execute(
                "SELECT * FROM papers WHERE source = ? AND source_id = ?", (source, source_id)
            ).fetchone()
        )

    def list_by_run(self, run_id: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM papers WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall()
        )


class RunsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, s: RunSummary, profile_slug: str, schedule_mode: str) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO runs (
                run_id, profile_slug, schedule_mode, started_at, ended_at,
                status, sources_json, raw_count, normalized_count, deduped_count,
                filtered_count, failed_count, report_path, log_path, dry_run
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                s.run_id,
                profile_slug,
                schedule_mode,
                s.started_at,
                s.ended_at,
                s.status,
                json.dumps([sr.model_dump() for sr in s.sources]),
                s.raw_count,
                s.normalized_count,
                s.deduped_count,
                s.filtered_count,
                s.failed_count,
                s.report_path,
                s.log_path,
                1 if s.dry_run else 0,
            ),
        )
        return _insert_id(cur)

    def update_summary(self, s: RunSummary) -> None:
        self.conn.execute(
            """
            UPDATE runs SET
                ended_at=?, status=?, sources_json=?, raw_count=?, normalized_count=?,
                deduped_count=?, filtered_count=?, failed_count=?, report_path=?, log_path=?
            WHERE run_id=?
            """,
            (
                s.ended_at,
                s.status,
                json.dumps([sr.model_dump() for sr in s.sources]),
                s.raw_count,
                s.normalized_count,
                s.deduped_count,
                s.filtered_count,
                s.failed_count,
                s.report_path,
                s.log_path,
                s.run_id,
            ),
        )

    def get_by_run_id(self, run_id: str) -> sqlite3.Row | None:
        return _row(self.conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone())


class FilterDecisionsRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def log(
        self,
        run_id: str,
        paper_id: int | None,
        decision: str,
        reason_code: str | None,
        reason_text: str | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO filter_decisions (run_id, paper_id, decision, reason_code, reason_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, paper_id, decision, reason_code, reason_text, _now()),
        )

    def list_by_run(self, run_id: str) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM filter_decisions WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        )


class DedupCandidatesRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def insert(self, paper_id_a: int, paper_id_b: int, match_type: str, similarity: float) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO dedup_candidates (paper_id_a, paper_id_b, match_type, similarity, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (paper_id_a, paper_id_b, match_type, similarity, _now()),
        )
        return _insert_id(cur)

    def list_pending(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM dedup_candidates WHERE status='pending' ORDER BY id"
            ).fetchall()
        )
