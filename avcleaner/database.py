from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import database_path

SCHEMA_VERSION = 3


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS scans (
            scan_id TEXT PRIMARY KEY,
            root_path TEXT NOT NULL,
            request_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scan_items (
            id TEXT PRIMARY KEY,
            scan_id TEXT NOT NULL,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            name TEXT NOT NULL,
            extension TEXT NOT NULL,
            kind TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            item_json TEXT NOT NULL,
            FOREIGN KEY(scan_id) REFERENCES scans(scan_id)
        );

        CREATE TABLE IF NOT EXISTS plans (
            plan_id TEXT PRIMARY KEY,
            scan_id TEXT NOT NULL,
            root_path TEXT NOT NULL,
            state TEXT NOT NULL,
            plan_hash TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            rules_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS plan_items (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            scan_item_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            source_path TEXT NOT NULL,
            source_rel_path TEXT NOT NULL,
            target_path TEXT NOT NULL,
            target_rel_path TEXT NOT NULL,
            target_name TEXT NOT NULL,
            suggestion_source TEXT NOT NULL,
            confidence REAL NOT NULL,
            selected_default INTEGER NOT NULL,
            requires_review INTEGER NOT NULL,
            requires_two_step INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL,
            trace_json TEXT NOT NULL,
            item_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
        );

        CREATE TABLE IF NOT EXISTS plan_validation_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id TEXT NOT NULL,
            item_id TEXT,
            code TEXT NOT NULL,
            severity TEXT NOT NULL,
            message_key TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            plan_id TEXT,
            plan_hash TEXT,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'created',
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS run_items (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            plan_item_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            state TEXT NOT NULL,
            source_path TEXT NOT NULL,
            target_path TEXT NOT NULL,
            temp_path TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            issue_code TEXT NOT NULL DEFAULT '',
            snapshot_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS quarantine_manifests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            original_abs_path TEXT NOT NULL,
            original_rel_path TEXT NOT NULL,
            quarantine_abs_path TEXT NOT NULL,
            size INTEGER NOT NULL,
            created_ns INTEGER NOT NULL,
            modified_ns INTEGER NOT NULL,
            reason TEXT NOT NULL,
            restore_status TEXT NOT NULL,
            manifest_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS llm_suggestion_cache (
            cache_key TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            payload_hash TEXT NOT NULL DEFAULT '',
            output_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS llm_suggestions (
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
            created_at TEXT NOT NULL,
            accepted_at TEXT NOT NULL DEFAULT '',
            rejected_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(plan_id) REFERENCES plans(plan_id)
        );
        """
    )

    if "schema_version" not in _table_columns(conn, "settings"):
        _add_column(conn, "settings", "schema_version", "INTEGER NOT NULL DEFAULT 1")

    _add_column(conn, "llm_suggestion_cache", "payload_hash", "TEXT NOT NULL DEFAULT ''")
    _add_column(conn, "llm_suggestions", "accepted_at", "TEXT NOT NULL DEFAULT ''")
    _add_column(conn, "llm_suggestions", "rejected_at", "TEXT NOT NULL DEFAULT ''")

    for column, ddl in {
        "plan_id": "TEXT",
        "plan_hash": "TEXT",
        "state": "TEXT NOT NULL DEFAULT 'created'",
        "created_at": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    }.items():
        _add_column(conn, "runs", column, ddl)

    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, utc_now_iso()),
    )
    conn.commit()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def loads(value: str) -> Any:
    return json.loads(value)


def load_setting(key: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    return loads(row["value"])


def save_setting(key: str, value: dict, schema_version: int = SCHEMA_VERSION) -> None:
    payload = dumps(value)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value, updated_at, schema_version)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at,
                schema_version = excluded.schema_version
            """,
            (key, payload, utc_now_iso(), schema_version),
        )
        conn.commit()
