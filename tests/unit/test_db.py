import sqlite3
from pathlib import Path

from src.storage.db import open_db, apply_migrations, MIGRATIONS_DIR


def test_open_db_creates_file(tmp_path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    assert db_path.exists()
    conn.close()


def test_apply_migrations_creates_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    apply_migrations(conn)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cur.fetchall()}
    assert {"papers", "runs", "filter_decisions", "dedup_candidates", "schema_versions"} <= tables
    conn.close()


def test_apply_migrations_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    apply_migrations(conn)
    apply_migrations(conn)  # second call should not error
    cur = conn.execute("SELECT version FROM schema_versions ORDER BY version")
    versions = [row[0] for row in cur.fetchall()]
    assert versions == [1]
    conn.close()


def test_migrations_dir_has_001():
    assert (MIGRATIONS_DIR / "001_initial.sql").exists()
