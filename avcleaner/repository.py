from __future__ import annotations

import os
import uuid
from collections import Counter
from pathlib import Path
from typing import Iterable

from .database import connect, dumps, loads, utc_now_iso
from .enums import PlanState, RunItemState, RunState
from .models import (
    ExecutionItem,
    ExecutionRun,
    LLMSuggestionRecord,
    PlanItem,
    PlanRecord,
    QuarantineManifest,
    RunSummary,
    ScanItem,
    ScanRequest,
    ScanResponse,
    ValidationIssue,
)

RECENT_FOLDERS_LIMIT = 10
TERMINAL_RUN_STATES = {
    RunState.PARTIAL_SUCCESS,
    RunState.SUCCESS,
    RunState.FAILED,
    RunState.ROLLED_BACK,
    RunState.ROLLBACK_PARTIAL,
    RunState.INTERRUPTED,
    RunState.CANCELLED,
    RunState.ABANDONED,
}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def create_scan(request: ScanRequest, response: ScanResponse) -> ScanResponse:
    scan_id = response.scan_id or new_id("scan")
    now = utc_now_iso()
    files = [
        item.model_copy(update={"scan_id": scan_id, "id": f"{scan_id}_{item.id}"})
        for item in response.files
    ]
    with connect() as conn:
        conn.execute(
            "INSERT INTO scans(scan_id, root_path, request_json, created_at) VALUES (?, ?, ?, ?)",
            (scan_id, response.root_path, dumps(request.model_dump(mode="json")), now),
        )
        conn.executemany(
            """
            INSERT INTO scan_items(
                id, scan_id, path, relative_path, name, extension, kind, snapshot_json, item_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.id,
                    scan_id,
                    item.path,
                    item.relative_path,
                    item.name,
                    item.extension,
                    item.kind,
                    dumps(item.snapshot.model_dump(mode="json") if item.snapshot else {}),
                    dumps(item.model_dump(mode="json")),
                )
                for item in files
            ],
        )
        conn.commit()
    return response.model_copy(update={"scan_id": scan_id, "files": files})


def get_scan(scan_id: str) -> ScanResponse:
    with connect() as conn:
        scan = conn.execute("SELECT scan_id, root_path FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
        if not scan:
            raise KeyError("scan_not_found")
        rows = conn.execute("SELECT item_json FROM scan_items WHERE scan_id = ? ORDER BY relative_path", (scan_id,)).fetchall()
    files = [ScanItem.model_validate(loads(row["item_json"])) for row in rows]
    return ScanResponse(scan_id=scan["scan_id"], root_path=scan["root_path"], files=files, total_files=len(files))


def save_plan(record: PlanRecord, rules_json: dict | None = None) -> PlanRecord:
    now = utc_now_iso()
    created_at = record.created_at or now
    updated = record.model_copy(update={"created_at": created_at, "updated_at": now})
    with connect() as conn:
        conn.execute("DELETE FROM plan_validation_issues WHERE plan_id = ?", (updated.plan_id,))
        conn.execute("DELETE FROM plan_items WHERE plan_id = ?", (updated.plan_id,))
        conn.execute(
            """
            INSERT INTO plans(
                plan_id, scan_id, root_path, state, plan_hash, summary_json, rules_json,
                created_at, updated_at, preview_mode, llm_used, llm_mode, llm_applied_count,
                llm_invalid_count, llm_fallback_to_rule_count, messages_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                state = excluded.state,
                plan_hash = excluded.plan_hash,
                summary_json = excluded.summary_json,
                rules_json = excluded.rules_json,
                updated_at = excluded.updated_at,
                preview_mode = excluded.preview_mode,
                llm_used = excluded.llm_used,
                llm_mode = excluded.llm_mode,
                llm_applied_count = excluded.llm_applied_count,
                llm_invalid_count = excluded.llm_invalid_count,
                llm_fallback_to_rule_count = excluded.llm_fallback_to_rule_count,
                messages_json = excluded.messages_json
            """,
            (
                updated.plan_id,
                updated.scan_id,
                updated.root_path,
                updated.state,
                updated.plan_hash,
                dumps(updated.summary),
                dumps(rules_json or {}),
                created_at,
                now,
                updated.preview_mode,
                int(updated.llm_used),
                updated.llm_mode,
                updated.llm_applied_count,
                updated.llm_invalid_count,
                updated.llm_fallback_to_rule_count,
                dumps(updated.messages),
            ),
        )
        conn.executemany(
            """
            INSERT INTO plan_items(
                id, plan_id, scan_item_id, operation, source_path, source_rel_path, target_path,
                target_rel_path, target_name, suggestion_source, confidence, selected_default,
                requires_review, requires_two_step, snapshot_json, trace_json, item_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.id,
                    updated.plan_id,
                    item.scan_item_id,
                    str(item.operation or item.action),
                    item.source_path,
                    item.source_rel_path,
                    item.target_path,
                    item.target_rel_path,
                    item.target_name,
                    str(item.suggestion_source or item.source),
                    item.confidence,
                    int(item.selected_default),
                    int(item.requires_review),
                    int(item.requires_two_step),
                    dumps(item.snapshot.model_dump(mode="json") if item.snapshot else {}),
                    dumps([step.model_dump(mode="json") for step in item.trace]),
                    dumps(item.model_dump(mode="json")),
                    now,
                    now,
                )
                for item in updated.items
            ],
        )
        issues: list[tuple] = []
        for item in updated.items:
            for issue in item.issues:
                issues.append(
                    (
                        updated.plan_id,
                        item.id,
                        issue.code,
                        issue.severity,
                        issue.message_key or str(issue.code),
                        dumps(issue.details),
                        now,
                    )
                )
        conn.executemany(
            """
            INSERT INTO plan_validation_issues(plan_id, item_id, code, severity, message_key, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            issues,
        )
        conn.commit()
    return updated


def get_plan(plan_id: str) -> PlanRecord:
    with connect() as conn:
        plan = conn.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,)).fetchone()
        if not plan:
            raise KeyError("plan_not_found")
        rows = conn.execute("SELECT item_json FROM plan_items WHERE plan_id = ? ORDER BY source_rel_path", (plan_id,)).fetchall()
    items = [PlanItem.model_validate(loads(row["item_json"])) for row in rows]
    return PlanRecord(
        plan_id=plan["plan_id"],
        scan_id=plan["scan_id"],
        root_path=plan["root_path"],
        state=PlanState(plan["state"]),
        plan_hash=plan["plan_hash"],
        summary=loads(plan["summary_json"]),
        items=items,
        created_at=plan["created_at"],
        updated_at=plan["updated_at"],
        preview_mode=plan["preview_mode"] if "preview_mode" in plan.keys() else "rule",
        llm_used=bool(plan["llm_used"]) if "llm_used" in plan.keys() else False,
        llm_mode=plan["llm_mode"] if "llm_mode" in plan.keys() else "",
        llm_applied_count=plan["llm_applied_count"] if "llm_applied_count" in plan.keys() else 0,
        llm_invalid_count=plan["llm_invalid_count"] if "llm_invalid_count" in plan.keys() else 0,
        llm_fallback_to_rule_count=plan["llm_fallback_to_rule_count"] if "llm_fallback_to_rule_count" in plan.keys() else 0,
        messages=loads(plan["messages_json"]) if "messages_json" in plan.keys() and plan["messages_json"] else [],
    )


def update_plan_state(plan_id: str, state: PlanState, plan_hash: str | None = None) -> None:
    with connect() as conn:
        if plan_hash:
            conn.execute(
                "UPDATE plans SET state = ?, plan_hash = ?, updated_at = ? WHERE plan_id = ?",
                (state, plan_hash, utc_now_iso(), plan_id),
            )
        else:
            conn.execute("UPDATE plans SET state = ?, updated_at = ? WHERE plan_id = ?", (state, utc_now_iso(), plan_id))
        conn.commit()


def create_run(run: ExecutionRun) -> ExecutionRun:
    now = utc_now_iso()
    updated = run.model_copy(update={"created_at": run.created_at or now, "updated_at": now})
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runs(
                run_id, plan_id, plan_hash, timestamp, status, state, summary,
                created_at, updated_at, completed_at, rollback_available
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                updated.run_id,
                updated.plan_id,
                updated.plan_hash,
                updated.created_at,
                updated.state,
                updated.state,
                dumps(updated.summary),
                updated.created_at,
                updated.updated_at,
                updated.completed_at,
                int(updated.rollback_available),
            ),
        )
        conn.commit()
    return updated


def _run_has_rollbackable_summary(summary: dict[str, int]) -> bool:
    return bool(summary.get(str(RunItemState.RENAMED)) or summary.get(str(RunItemState.QUARANTINED)))


def update_run_state(run_id: str, state: RunState, summary: dict[str, int] | None = None) -> None:
    with connect() as conn:
        if summary is None:
            row = conn.execute("SELECT summary FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            summary_json = row["summary"] if row else "{}"
            summary_payload = loads(summary_json)
        else:
            summary_json = dumps(summary)
            summary_payload = summary
        now = utc_now_iso()
        completed_at = now if state in TERMINAL_RUN_STATES else ""
        rollback_available = int(state in {RunState.SUCCESS, RunState.PARTIAL_SUCCESS} and _run_has_rollbackable_summary(summary_payload))
        conn.execute(
            """
            UPDATE runs
            SET state = ?, status = ?, summary = ?, updated_at = ?,
                completed_at = CASE WHEN ? != '' THEN ? ELSE completed_at END,
                rollback_available = ?
            WHERE run_id = ?
            """,
            (state, state, summary_json, now, completed_at, completed_at, rollback_available, run_id),
        )
        conn.commit()


def upsert_run_item(item: ExecutionItem) -> ExecutionItem:
    now = utc_now_iso()
    updated = item.model_copy(update={"created_at": item.created_at or now, "updated_at": now})
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO run_items(
                id, run_id, plan_item_id, operation, state, source_path, target_path, temp_path,
                message, issue_code, snapshot_json, created_at, updated_at, rollback_status,
                rollback_error_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                state = excluded.state,
                target_path = excluded.target_path,
                temp_path = excluded.temp_path,
                message = excluded.message,
                issue_code = excluded.issue_code,
                snapshot_json = excluded.snapshot_json,
                rollback_status = excluded.rollback_status,
                rollback_error_code = excluded.rollback_error_code,
                updated_at = excluded.updated_at
            """,
            (
                updated.id,
                updated.run_id,
                updated.plan_item_id,
                updated.operation,
                updated.state,
                updated.source_path,
                updated.target_path,
                updated.temp_path,
                updated.message,
                updated.issue_code,
                dumps(updated.snapshot.model_dump(mode="json") if updated.snapshot else {}),
                updated.created_at,
                updated.updated_at,
                updated.rollback_status,
                updated.rollback_error_code,
            ),
        )
        conn.commit()
    return updated


def get_run_items(run_id: str, reverse: bool = False) -> list[ExecutionItem]:
    order = "DESC" if reverse else "ASC"
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM run_items WHERE run_id = ? ORDER BY created_at {order}, id {order}", (run_id,)).fetchall()
    return [
        ExecutionItem(
            id=row["id"],
            run_id=row["run_id"],
            plan_item_id=row["plan_item_id"],
            operation=row["operation"],
            state=row["state"],
            source_path=row["source_path"],
            target_path=row["target_path"],
            temp_path=row["temp_path"],
            message=row["message"],
            issue_code=row["issue_code"],
            snapshot=loads(row["snapshot_json"]) if row["snapshot_json"] and row["snapshot_json"] != "{}" else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            rollback_status=row["rollback_status"] if "rollback_status" in row.keys() else "",
            rollback_error_code=row["rollback_error_code"] if "rollback_error_code" in row.keys() else "",
        )
        for row in rows
    ]


def get_run(run_id: str) -> ExecutionRun:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            raise KeyError("run_not_found")
    return ExecutionRun(
        run_id=row["run_id"],
        plan_id=row["plan_id"] or "",
        plan_hash=row["plan_hash"] or "",
        state=RunState(row["state"]),
        summary=loads(row["summary"]),
        created_at=row["created_at"] or row["timestamp"],
        updated_at=row["updated_at"] or row["timestamp"],
        completed_at=row["completed_at"] if "completed_at" in row.keys() else "",
        rollback_available=bool(row["rollback_available"]) if "rollback_available" in row.keys() else False,
    )


def list_runs(limit: int = 50) -> list[RunSummary]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT run_id, timestamp, status, state, summary, completed_at, rollback_available
            FROM runs
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        RunSummary(
            run_id=row["run_id"],
            timestamp=row["timestamp"],
            status=row["status"],
            state=row["state"],
            summary=loads(row["summary"]),
            completed_at=row["completed_at"] if "completed_at" in row.keys() else "",
            rollback_available=bool(row["rollback_available"]) if "rollback_available" in row.keys() else False,
        )
        for row in rows
    ]


def update_run_item_rollback_status(item_id: str, status: str, error_code: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE run_items
            SET rollback_status = ?, rollback_error_code = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, error_code, utc_now_iso(), item_id),
        )
        conn.commit()


def _recent_folder_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(path)).lower()


def upsert_recent_folder(
    path: str,
    *,
    last_scan_id: str = "",
    last_plan_id: str = "",
    item_count: int = 0,
    mode: str = "dev",
    limit: int = RECENT_FOLDERS_LIMIT,
) -> dict:
    clean_path = os.path.abspath(path)
    key = _recent_folder_key(clean_path)
    display_name = Path(clean_path).name or clean_path
    now = utc_now_iso()
    with connect() as conn:
        existing = conn.execute("SELECT * FROM recent_folders WHERE path_key = ?", (key,)).fetchone()
        next_scan_id = last_scan_id or (existing["last_scan_id"] if existing else "")
        next_plan_id = last_plan_id or (existing["last_plan_id"] if existing else "")
        next_item_count = item_count if item_count else (existing["item_count"] if existing else 0)
        next_mode = mode or (existing["mode"] if existing else "dev")
        conn.execute(
            """
            INSERT INTO recent_folders(
                path_key, path, display_name, last_used_at, last_scan_id, last_plan_id, item_count, mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path_key) DO UPDATE SET
                path = excluded.path,
                display_name = excluded.display_name,
                last_used_at = excluded.last_used_at,
                last_scan_id = excluded.last_scan_id,
                last_plan_id = excluded.last_plan_id,
                item_count = excluded.item_count,
                mode = excluded.mode
            """,
            (key, clean_path, display_name, now, next_scan_id, next_plan_id, next_item_count, next_mode),
        )
        conn.execute(
            """
            DELETE FROM recent_folders
            WHERE path_key NOT IN (
                SELECT path_key FROM recent_folders ORDER BY last_used_at DESC LIMIT ?
            )
            """,
            (limit,),
        )
        conn.commit()
    return {
        "path": clean_path,
        "display_name": display_name,
        "last_used_at": now,
        "last_scan_id": next_scan_id,
        "last_plan_id": next_plan_id,
        "item_count": next_item_count,
        "mode": next_mode,
    }


def list_recent_folders(limit: int = RECENT_FOLDERS_LIMIT) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT path, display_name, last_used_at, last_scan_id, last_plan_id, item_count, mode
            FROM recent_folders
            ORDER BY last_used_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "path": row["path"],
            "display_name": row["display_name"],
            "last_used_at": row["last_used_at"],
            "last_scan_id": row["last_scan_id"],
            "last_plan_id": row["last_plan_id"],
            "item_count": row["item_count"],
            "mode": row["mode"],
        }
        for row in rows
    ]


def clear_recent_folders() -> int:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM recent_folders")
        conn.commit()
        return cursor.rowcount


def get_local_ui_state(key: str) -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM local_ui_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else ""


def set_local_ui_state(key: str, value: str) -> dict:
    now = utc_now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO local_ui_state(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, value, now),
        )
        conn.commit()
    return {"key": key, "value": value, "updated_at": now}


def mark_interrupted_runs() -> int:
    with connect() as conn:
        rows = conn.execute(
            "SELECT run_id FROM runs WHERE state IN (?, ?)",
            (RunState.RUNNING, RunState.ROLLBACK_RUNNING),
        ).fetchall()
        now = utc_now_iso()
        for row in rows:
            run_id = row["run_id"]
            conn.execute(
                """
                UPDATE run_items
                SET state = ?, message = ?, issue_code = ?, updated_at = ?
                WHERE run_id = ? AND state = ?
                """,
                (RunItemState.FAILED, "operation_interrupted", "operation_interrupted", now, run_id, RunItemState.PENDING),
            )
            item_rows = conn.execute("SELECT state, COUNT(*) AS count FROM run_items WHERE run_id = ? GROUP BY state", (run_id,)).fetchall()
            summary = {item_row["state"]: int(item_row["count"]) for item_row in item_rows}
            rollback_available = int(_run_has_rollbackable_summary(summary))
            conn.execute(
                """
                UPDATE runs
                SET state = ?, status = ?, summary = ?, updated_at = ?, completed_at = ?,
                    rollback_available = ?
                WHERE run_id = ?
                """,
                (RunState.INTERRUPTED, RunState.INTERRUPTED, dumps(summary), now, now, rollback_available, run_id),
            )
        conn.commit()
        return len(rows)


def save_quarantine_manifest(manifest: QuarantineManifest) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO quarantine_manifests(
                run_id, item_id, original_abs_path, original_rel_path, quarantine_abs_path,
                size, created_ns, modified_ns, reason, restore_status, manifest_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest.run_id,
                manifest.item_id,
                manifest.original_abs_path,
                manifest.original_rel_path,
                manifest.quarantine_abs_path,
                manifest.size,
                manifest.created_ns,
                manifest.modified_ns,
                manifest.reason,
                manifest.restore_status,
                dumps(manifest.model_dump(mode="json")),
                utc_now_iso(),
            ),
        )
        conn.commit()


def update_quarantine_manifest_restore_status(run_id: str, item_id: str, restore_status: str) -> None:
    with connect() as conn:
        row = conn.execute(
            "SELECT manifest_json FROM quarantine_manifests WHERE run_id = ? AND item_id = ?",
            (run_id, item_id),
        ).fetchone()
        if row is None:
            return
        payload = loads(row["manifest_json"])
        payload["restore_status"] = restore_status
        conn.execute(
            """
            UPDATE quarantine_manifests
            SET restore_status = ?, manifest_json = ?
            WHERE run_id = ? AND item_id = ?
            """,
            (restore_status, dumps(payload), run_id, item_id),
        )
        conn.commit()


def create_llm_suggestion(record: LLMSuggestionRecord) -> LLMSuggestionRecord:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_suggestions(
                suggestion_id, plan_id, item_id, provider, model, schema_version, payload_hash,
                response_hash, suggested_name, parsed_json, validation_json, status, created_at,
                accepted_at, rejected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.suggestion_id,
                record.plan_id,
                record.item_id,
                record.provider,
                record.model,
                record.schema_version,
                record.payload_hash,
                record.response_hash,
                record.suggested_name,
                dumps(
                    {
                        "suggestion_id": record.suggestion_id,
                        "plan_id": record.plan_id,
                        "item_id": record.item_id,
                        "provider": record.provider,
                        "model": record.model,
                        "schema_version": record.schema_version,
                        "suggested_name": record.suggested_name,
                        "media_code": record.media_code,
                        "part_suffix": record.part_suffix,
                        "variant": record.variant,
                        "language_suffix": record.language_suffix,
                        "removed_tokens": record.removed_tokens,
                        "confidence": record.confidence,
                        "reason": record.reason,
                        "warnings": record.warnings,
                        "status": record.status,
                        "created_at": record.created_at,
                        "payload_hash": record.payload_hash,
                        "response_hash": record.response_hash,
                        "generated_plan_hash": record.generated_plan_hash,
                        "accepted_at": record.accepted_at,
                        "rejected_at": record.rejected_at,
                    }
                ),
                dumps([issue.model_dump(mode="json") for issue in record.validation_issues]),
                record.status,
                record.created_at,
                record.accepted_at,
                record.rejected_at,
            ),
        )
        conn.commit()
    return record


def _llm_record_from_row(row) -> LLMSuggestionRecord:
    payload = loads(row["parsed_json"])
    payload.update(
        {
            "status": row["status"],
            "accepted_at": row["accepted_at"] or "",
            "rejected_at": row["rejected_at"] or "",
            "validation_issues": loads(row["validation_json"]),
        }
    )
    return LLMSuggestionRecord.model_validate(payload)


def list_llm_suggestions(plan_id: str) -> list[LLMSuggestionRecord]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM llm_suggestions WHERE plan_id = ? ORDER BY created_at DESC, suggestion_id DESC",
            (plan_id,),
        ).fetchall()
    return [_llm_record_from_row(row) for row in rows]


def get_llm_suggestion(suggestion_id: str) -> LLMSuggestionRecord:
    with connect() as conn:
        row = conn.execute("SELECT * FROM llm_suggestions WHERE suggestion_id = ?", (suggestion_id,)).fetchone()
    if not row:
        raise KeyError("suggestion_not_found")
    return _llm_record_from_row(row)


def update_llm_suggestion_status(suggestion_id: str, status: str, *, accepted_at: str = "", rejected_at: str = "") -> LLMSuggestionRecord:
    with connect() as conn:
        existing = conn.execute("SELECT * FROM llm_suggestions WHERE suggestion_id = ?", (suggestion_id,)).fetchone()
        if not existing:
            raise KeyError("suggestion_not_found")
        payload = loads(existing["parsed_json"])
        payload["status"] = status
        if accepted_at:
            payload["accepted_at"] = accepted_at
        if rejected_at:
            payload["rejected_at"] = rejected_at
        conn.execute(
            """
            UPDATE llm_suggestions
            SET status = ?, accepted_at = CASE WHEN ? != '' THEN ? ELSE accepted_at END,
                rejected_at = CASE WHEN ? != '' THEN ? ELSE rejected_at END,
                parsed_json = ?
            WHERE suggestion_id = ?
            """,
            (status, accepted_at, accepted_at, rejected_at, rejected_at, dumps(payload), suggestion_id),
        )
        conn.commit()
    return get_llm_suggestion(suggestion_id)


def mark_llm_suggestions_stale(plan_id: str, item_id: str, except_suggestion_id: str = "") -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            UPDATE llm_suggestions
            SET status = 'stale'
            WHERE plan_id = ? AND item_id = ? AND status IN ('pending', 'valid', 'invalid') AND suggestion_id != ?
            """,
            (plan_id, item_id, except_suggestion_id),
        )
        conn.commit()
        return cursor.rowcount


def get_llm_cache(cache_key: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT output_json FROM llm_suggestion_cache WHERE cache_key = ?", (cache_key,)).fetchone()
    if not row:
        return None
    return loads(row["output_json"])


def save_llm_cache(
    cache_key: str,
    provider: str,
    model: str,
    schema_version: int,
    payload_hash: str,
    output_json: dict,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_suggestion_cache(cache_key, provider, model, input_hash, payload_hash, output_json, created_at, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                provider = excluded.provider,
                model = excluded.model,
                input_hash = excluded.input_hash,
                payload_hash = excluded.payload_hash,
                output_json = excluded.output_json,
                created_at = excluded.created_at,
                schema_version = excluded.schema_version
            """,
            (cache_key, provider, model, payload_hash, payload_hash, dumps(output_json), utc_now_iso(), schema_version),
        )
        conn.commit()


def summarize_item_states(items: Iterable[ExecutionItem]) -> dict[str, int]:
    return dict(Counter(str(item.state) for item in items))
