from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import OperationRecord, RunSummary
from .paths import database_path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            source_path TEXT NOT NULL,
            target_path TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            size INTEGER NOT NULL DEFAULT 0,
            mtime REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(run_id) REFERENCES runs(run_id)
        );
        """
    )
    conn.commit()


def load_setting(key: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    return json.loads(row["value"])


def save_setting(key: str, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True)
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, payload, utc_now_iso()),
        )
        conn.commit()


def write_run(run_id: str, operations: Iterable[OperationRecord]) -> None:
    ops = list(operations)
    summary = dict(Counter(f"{op.action}:{op.status}" for op in ops))
    status = "ok" if all(op.status in {"OK", "Skipped"} for op in ops) else "partial"
    timestamp = utc_now_iso()
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs(run_id, timestamp, status, summary) VALUES (?, ?, ?, ?)",
            (run_id, timestamp, status, json.dumps(summary, ensure_ascii=False, sort_keys=True)),
        )
        conn.executemany(
            """
            INSERT INTO operations(
                run_id, timestamp, action, source_path, target_path, status, message, size, mtime
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    op.run_id,
                    op.timestamp,
                    op.action,
                    op.source_path,
                    op.target_path,
                    op.status,
                    op.message,
                    op.size,
                    op.mtime,
                )
                for op in ops
            ],
        )
        conn.commit()


def list_runs(limit: int = 50) -> list[RunSummary]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT run_id, timestamp, status, summary FROM runs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        RunSummary(
            run_id=row["run_id"],
            timestamp=row["timestamp"],
            status=row["status"],
            summary=json.loads(row["summary"]),
        )
        for row in rows
    ]


def operations_for_run(run_id: str) -> list[OperationRecord]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT run_id, timestamp, action, source_path, target_path, status, message, size, mtime
            FROM operations
            WHERE run_id = ?
            ORDER BY id DESC
            """,
            (run_id,),
        ).fetchall()
    return [OperationRecord(**dict(row)) for row in rows]

