from __future__ import annotations

import sqlite3
from pathlib import Path

from avcleaner.database import SCHEMA_VERSION, connect


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_v070_fresh_db_has_recent_folders_and_rollback_fields(tmp_path: Path) -> None:
    with connect(tmp_path / "fresh-v070.db") as conn:
        names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        migration = conn.execute("SELECT version FROM schema_migrations WHERE version = ?", (SCHEMA_VERSION,)).fetchone()

        assert "recent_folders" in names
        assert {"completed_at", "rollback_available"} <= columns(conn, "runs")
        assert {"rollback_status", "rollback_error_code"} <= columns(conn, "run_items")
        assert migration["version"] == SCHEMA_VERSION


def test_v070_old_db_migration_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "old-v070.db"
    raw = sqlite3.connect(db_path)
    try:
        raw.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        raw.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (3, '2026-01-01T00:00:00+00:00')")
        raw.execute("CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
        raw.execute("CREATE TABLE runs(run_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL)")
        raw.commit()
    finally:
        raw.close()

    with connect(db_path) as conn:
        from avcleaner.database import init_db

        init_db(conn)
        init_db(conn)
        migration_count = conn.execute(
            "SELECT COUNT(*) AS count FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()["count"]
        assert "recent_folders" in {
            row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert {"completed_at", "rollback_available"} <= columns(conn, "runs")
        assert migration_count == 1
