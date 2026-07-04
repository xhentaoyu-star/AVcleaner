from __future__ import annotations

import sqlite3
from pathlib import Path

from avcleaner.database import SCHEMA_VERSION, connect, dumps, loads
from avcleaner.secrets import InMemorySecretStore
from avcleaner.settings_store import get_settings


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def create_v2_like_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (2, '2026-01-01T00:00:00+00:00')")
        conn.execute("CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE runs(run_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO runs(run_id, timestamp, status, summary) VALUES ('run_old', '2026-01-01T00:00:00+00:00', 'success', '{}')"
        )
        conn.commit()
    finally:
        conn.close()


def create_v4_like_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (3, '2026-01-01T00:00:00+00:00')")
        conn.execute(
            """
            CREATE TABLE llm_suggestions(
                suggestion_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                payload_hash TEXT NOT NULL,
                response_hash TEXT NOT NULL,
                suggested_name TEXT NOT NULL,
                parsed_json TEXT NOT NULL,
                validation_json TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_fresh_db_initializes_latest_schema(tmp_path: Path) -> None:
    with connect(tmp_path / "fresh.db") as conn:
        row = conn.execute("SELECT version FROM schema_migrations WHERE version = ?", (SCHEMA_VERSION,)).fetchone()

    assert row["version"] == SCHEMA_VERSION


def test_v2_like_db_migrates_to_latest_and_preserves_run(tmp_path: Path) -> None:
    db_path = tmp_path / "old-v2.db"
    create_v2_like_db(db_path)

    with connect(db_path) as conn:
        assert {"state", "plan_id", "plan_hash", "created_at", "updated_at"} <= columns(conn, "runs")
        assert "schema_version" in columns(conn, "settings")
        row = conn.execute("SELECT status FROM runs WHERE run_id = 'run_old'").fetchone()
        migration = conn.execute("SELECT version FROM schema_migrations WHERE version = ?", (SCHEMA_VERSION,)).fetchone()

    assert row["status"] == "success"
    assert migration["version"] == SCHEMA_VERSION


def test_v4_like_llm_suggestions_table_migrates_without_breaking(tmp_path: Path) -> None:
    db_path = tmp_path / "old-v4.db"
    create_v4_like_db(db_path)

    with connect(db_path) as conn:
        names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "llm_suggestions" in names
        assert "llm_suggestion_cache" in names
        assert {"accepted_at", "rejected_at"} <= columns(conn, "llm_suggestions")


def test_migration_is_idempotent_on_old_db(tmp_path: Path) -> None:
    db_path = tmp_path / "old-idempotent.db"
    create_v2_like_db(db_path)

    with connect(db_path) as conn:
        from avcleaner.database import init_db

        init_db(conn)
        init_db(conn)
        row = conn.execute("SELECT COUNT(*) AS count FROM schema_migrations WHERE version = ?", (SCHEMA_VERSION,)).fetchone()

    assert row["count"] == 1


def test_old_settings_api_key_is_migrated_out_of_sqlite(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    db_path = state_dir / "avcleaner.db"
    monkeypatch.setenv("AVCLEANER_DATA_DIR", str(state_dir))
    create_v2_like_db(db_path)
    old_settings = {
        "llm": {
            "provider": "openai_compatible",
            "base_url": "https://example.invalid",
            "api_key": "secret-value",
            "model": "mock",
            "temperature": 0.0,
            "max_batch_size": 20,
            "max_concurrency": 2,
            "send_full_path": False,
            "min_confidence": 0.7,
        }
    }
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO settings(key, value, updated_at, schema_version) VALUES ('app_settings', ?, '2026-01-01T00:00:00+00:00', 1)",
            (dumps(old_settings),),
        )
        conn.commit()

    store = InMemorySecretStore()
    loaded = get_settings(store)

    with connect(db_path) as conn:
        persisted = loads(conn.execute("SELECT value FROM settings WHERE key = 'app_settings'").fetchone()["value"])

    assert loaded.llm.api_key == ""
    assert persisted["llm"]["api_key"] == ""
    assert store.get_api_key("openai_compatible") == "secret-value"
