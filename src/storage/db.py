"""SQLite connection management and migrations."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def open_db(db_path: Path | str) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    try:
        cur = conn.execute("SELECT version FROM schema_versions")
        return {row[0] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        return set()


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply unapplied migrations from migrations/ in lexical order."""
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    applied = _applied_versions(conn)
    for f in files:
        version = int(f.name.split("_")[0])
        if version in applied:
            continue
        sql = f.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_versions(version, applied_at) VALUES (?, ?)",
            (version, datetime.now(UTC).isoformat()),
        )
