from pathlib import Path

from src.storage.db import MIGRATIONS_DIR, apply_migrations, open_db


def test_open_db_creates_file(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    assert db_path.exists()
    conn.close()


def test_apply_migrations_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    apply_migrations(conn)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cur.fetchall()}
    assert {"papers", "runs", "filter_decisions", "dedup_candidates", "schema_versions"} <= tables
    conn.close()


def test_apply_migrations_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = open_db(db_path)
    apply_migrations(conn)
    apply_migrations(conn)  # second call should not error
    cur = conn.execute("SELECT version FROM schema_versions ORDER BY version")
    versions = [row[0] for row in cur.fetchall()]
    assert versions == [1, 2]
    conn.close()


def test_migrations_dir_has_001() -> None:
    assert (MIGRATIONS_DIR / "001_initial.sql").exists()
