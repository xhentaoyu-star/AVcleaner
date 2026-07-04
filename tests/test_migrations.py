from __future__ import annotations

from avcleaner.database import connect, init_db


def test_schema_migrations_table_exists() -> None:
    with connect() as conn:
        row = conn.execute("SELECT version FROM schema_migrations WHERE version = 3").fetchone()
    assert row["version"] == 3


def test_core_tables_exist() -> None:
    with connect() as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {row["name"] for row in rows}
    assert {
        "scans",
        "scan_items",
        "plans",
        "plan_items",
        "runs",
        "run_items",
        "quarantine_manifests",
        "llm_suggestions",
        "llm_suggestion_cache",
    } <= names


def test_migrations_are_idempotent() -> None:
    with connect() as conn:
        init_db(conn)
        init_db(conn)
        rows = conn.execute("SELECT COUNT(*) AS count FROM schema_migrations WHERE version = 3").fetchone()
    assert rows["count"] == 1


def test_settings_has_schema_version() -> None:
    with connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(settings)").fetchall()}
    assert "schema_version" in columns


def test_runs_table_keeps_state_columns() -> None:
    with connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()}
    assert {"state", "plan_id", "plan_hash"} <= columns
