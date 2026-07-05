from __future__ import annotations

import sqlite3
from pathlib import Path

from avcleaner.database import SCHEMA_VERSION, connect, init_db


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_v071_fresh_db_has_preview_metadata_and_local_ui_state(tmp_path: Path) -> None:
    with connect(tmp_path / "fresh-v071.db") as conn:
        names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        migration = conn.execute("SELECT version FROM schema_migrations WHERE version = ?", (SCHEMA_VERSION,)).fetchone()

        assert "local_ui_state" in names
        assert {
            "preview_mode",
            "llm_used",
            "llm_mode",
            "llm_applied_count",
            "llm_invalid_count",
            "llm_fallback_to_rule_count",
            "messages_json",
        } <= columns(conn, "plans")
        assert migration["version"] == SCHEMA_VERSION


def test_v071_old_db_migration_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "old-v071.db"
    raw = sqlite3.connect(db_path)
    try:
        raw.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        raw.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (4, '2026-01-01T00:00:00+00:00')")
        raw.execute("CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
        raw.execute(
            """
            CREATE TABLE plans(
                plan_id TEXT PRIMARY KEY, scan_id TEXT NOT NULL, root_path TEXT NOT NULL,
                state TEXT NOT NULL, plan_hash TEXT NOT NULL, summary_json TEXT NOT NULL,
                rules_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )
        raw.commit()
    finally:
        raw.close()

    with connect(db_path) as conn:
        init_db(conn)
        init_db(conn)
        migration_count = conn.execute(
            "SELECT COUNT(*) AS count FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()["count"]

        assert "local_ui_state" in {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {"preview_mode", "messages_json"} <= columns(conn, "plans")
        assert migration_count == 1
