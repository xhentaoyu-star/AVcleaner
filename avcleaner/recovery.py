from __future__ import annotations

import csv
import io
from pathlib import Path

from .csv_export import safe_csv_row
from typing import Iterable

from .enums import Operation, RunItemState, RunState
from .errors import AppError
from .fingerprint import snapshot_for_path
from .models import ExecutionItem, ExecutionRun, FileSnapshot, PlanItem, PlanRecord
from .repository import get_plan, get_run, get_run_items

ROLLBACK_TARGET_EXISTS = "rollback_target_exists"
ROLLBACK_SOURCE_MISSING = "rollback_source_missing"
QUARANTINE_FILE_MISSING = "quarantine_file_missing"
ROLLBACK_FILE_CHANGED = "rollback_file_changed"
UNKNOWN_RUN_ITEM = "unknown_run_item"
ROLLBACK_ALREADY_COMPLETED = "rollback_already_completed"
ROLLBACK_NOT_AVAILABLE = "rollback_not_available"

ROLLBACKABLE_STATES = {RunItemState.RENAMED, RunItemState.QUARANTINED}
SUCCESS_STATES = {RunItemState.RENAMED, RunItemState.QUARANTINED, RunItemState.SKIPPED, RunItemState.ROLLED_BACK}
FAILED_STATES = {RunItemState.FAILED, RunItemState.ROLLBACK_FAILED}


def is_rollbackable_item(item: ExecutionItem) -> bool:
    return item.state in ROLLBACKABLE_STATES or (item.state == RunItemState.FAILED and bool(item.temp_path))


def _rollback_current_path(item: ExecutionItem) -> Path:
    if item.state == RunItemState.FAILED and item.temp_path:
        return Path(item.temp_path).resolve(strict=False)
    return Path(item.target_path).resolve(strict=False)


def _display_safe_root(root_path: str) -> dict:
    if not root_path:
        return {}
    path = Path(root_path)
    return {
        "display_name": path.name or root_path,
        "anchor": path.anchor.rstrip("\\/"),
        "redacted": True,
    }


def _load_plan_for_run(run: ExecutionRun) -> PlanRecord | None:
    if not run.plan_id:
        return None
    try:
        return get_plan(run.plan_id)
    except KeyError:
        try:
            source_run = get_run(run.plan_id)
            return get_plan(source_run.plan_id)
        except KeyError:
            return None


def _plan_items_by_id(plan: PlanRecord | None) -> dict[str, PlanItem]:
    if not plan:
        return {}
    return {item.id: item for item in plan.items}


def _rel_from_path(path: str) -> str:
    return Path(path).name if path else ""


def _issue_codes(run_item: ExecutionItem, plan_item: PlanItem | None) -> list[str]:
    codes: list[str] = []
    if plan_item:
        codes.extend(plan_item.issue_codes)
    if run_item.issue_code:
        codes.append(run_item.issue_code)
    if run_item.rollback_error_code:
        codes.append(run_item.rollback_error_code)
    return sorted(set(str(code) for code in codes if code))


def _reason_codes(plan_item: PlanItem | None) -> list[str]:
    if not plan_item:
        return []
    codes = [str(code) for code in plan_item.review_reason_codes if code]
    if plan_item.reason:
        codes.append(plan_item.reason)
    return sorted(set(codes))


def _trace_summary(plan_item: PlanItem | None) -> list[dict]:
    if not plan_item:
        return []
    return [
        {
            "rule_id": step.rule_id,
            "before": step.before,
            "after": step.after,
            "warnings": step.warnings,
        }
        for step in plan_item.trace
    ]


def _run_item_record(run_item: ExecutionItem, plan_item: PlanItem | None) -> dict:
    source_name = plan_item.original_name if plan_item else Path(run_item.source_path).name
    target_name = (plan_item.target_name or plan_item.suggested_name) if plan_item else Path(run_item.target_path).name
    return {
        "item_id": run_item.id,
        "plan_item_id": run_item.plan_item_id,
        "operation": str(run_item.operation),
        "status": str(run_item.state),
        "source_name": source_name,
        "target_name": target_name,
        "source_rel_path": plan_item.source_rel_path if plan_item else _rel_from_path(run_item.source_path),
        "target_rel_path": plan_item.target_rel_path if plan_item else _rel_from_path(run_item.target_path),
        "size": plan_item.size if plan_item else (run_item.snapshot.size if run_item.snapshot else 0),
        "mtime": plan_item.mtime if plan_item else 0,
        "reason_codes": _reason_codes(plan_item),
        "issue_codes": _issue_codes(run_item, plan_item),
        "message_code": run_item.message,
        "message_summary": run_item.message,
        "sidecar_type": plan_item.sidecar_type if plan_item else None,
        "media_code": plan_item.media_code if plan_item else "",
        "language_suffix": plan_item.language_suffix if plan_item else "",
        "llm_accepted": bool(plan_item.llm_accepted) if plan_item else False,
        "manual_edited": bool(plan_item.manual_edited) if plan_item else False,
        "rollback_status": run_item.rollback_status,
        "rollback_error_code": run_item.rollback_error_code,
        "trace_summary": _trace_summary(plan_item),
    }


def _rollback_state(items: Iterable[ExecutionItem]) -> str:
    item_list = list(items)
    rollback_statuses = [item.rollback_status for item in item_list if item.rollback_status]
    if rollback_statuses and all(status == str(RunItemState.ROLLED_BACK) for status in rollback_statuses):
        return "rolled_back"
    if any(status == str(RunItemState.ROLLBACK_FAILED) for status in rollback_statuses):
        return "rollback_partial"
    if any(is_rollbackable_item(item) and item.rollback_status != str(RunItemState.ROLLED_BACK) for item in item_list):
        return "available"
    return "unavailable"


def _rollback_available(run: ExecutionRun, items: Iterable[ExecutionItem]) -> bool:
    if run.state in {RunState.ROLLED_BACK, RunState.ROLLBACK_RUNNING}:
        return False
    return any(is_rollbackable_item(item) and item.rollback_status != str(RunItemState.ROLLED_BACK) for item in items)


def build_run_detail(run_id: str) -> dict:
    run = get_run(run_id)
    run_items = get_run_items(run_id)
    plan = _load_plan_for_run(run)
    plan_items = _plan_items_by_id(plan)
    records = [_run_item_record(item, plan_items.get(item.plan_item_id)) for item in run_items]
    return {
        "run_id": run.run_id,
        "created_at": run.created_at,
        "completed_at": run.completed_at or run.updated_at,
        "state": str(run.state),
        "root_dir": _display_safe_root(plan.root_path if plan else ""),
        "plan_id": run.plan_id,
        "plan_hash": run.plan_hash,
        "ruleset_hash": next((item.ruleset_hash for item in plan.items if item.ruleset_hash), "") if plan else "",
        "selected_count": len(run_items),
        "success_count": sum(1 for item in run_items if item.state in SUCCESS_STATES),
        "failed_count": sum(1 for item in run_items if item.state in FAILED_STATES),
        "rollback_state": _rollback_state(run_items),
        "rollback_available": _rollback_available(run, run_items),
        "items": records,
    }


def _matches_snapshot(path: Path, snapshot: FileSnapshot | None) -> bool:
    if not snapshot:
        return True
    current = snapshot_for_path(path)
    return (
        current.size == snapshot.size
        and int(current.modified_ns) == int(snapshot.modified_ns)
        and current.fingerprint == snapshot.fingerprint
    )


def _selected_rollback_items(run_items: list[ExecutionItem], item_ids: list[str] | None) -> list[ExecutionItem]:
    by_id = {item.id: item for item in run_items}
    if item_ids is not None:
        unknown = sorted(set(item_ids) - set(by_id))
        if unknown:
            raise AppError(UNKNOWN_RUN_ITEM, 400)
        return [by_id[item_id] for item_id in item_ids]
    return [
        item
        for item in run_items
        if is_rollbackable_item(item) and item.rollback_status != str(RunItemState.ROLLED_BACK)
    ]


def _preview_item(item: ExecutionItem) -> dict:
    issue_codes: list[str] = []
    warnings: list[str] = []
    operation = str(item.operation)
    rollback_action = "skip"
    missing_code = ROLLBACK_SOURCE_MISSING
    current_path = _rollback_current_path(item)
    restore_target = Path(item.source_path).resolve(strict=False)

    if item.rollback_status == str(RunItemState.ROLLED_BACK):
        issue_codes.append(ROLLBACK_ALREADY_COMPLETED)
    elif item.state == RunItemState.RENAMED:
        rollback_action = "rename_back"
    elif item.state == RunItemState.QUARANTINED:
        rollback_action = "restore_from_quarantine"
        missing_code = QUARANTINE_FILE_MISSING
    elif item.state == RunItemState.FAILED and item.temp_path:
        rollback_action = "restore_temp_rename"
    else:
        issue_codes.append(ROLLBACK_NOT_AVAILABLE)

    current_path_status = "unknown"
    restore_target_status = "unknown"
    if rollback_action != "skip":
        if not current_path.exists():
            current_path_status = "missing"
            issue_codes.append(missing_code)
        else:
            try:
                current_path_status = "available" if _matches_snapshot(current_path, item.snapshot) else "changed"
                if current_path_status == "changed":
                    issue_codes.append(ROLLBACK_FILE_CHANGED)
            except OSError:
                current_path_status = "unknown"
                warnings.append("rollback_current_path_unknown")

        try:
            restore_target_status = "exists" if restore_target.exists() else "free"
            if restore_target_status == "exists":
                issue_codes.append(ROLLBACK_TARGET_EXISTS)
        except OSError:
            restore_target_status = "unknown"
            warnings.append("rollback_restore_target_unknown")

    blocking = bool(issue_codes)
    return {
        "item_id": item.id,
        "operation": operation,
        "current_path_status": current_path_status,
        "restore_target_status": restore_target_status,
        "rollback_action": rollback_action,
        "blocking": blocking,
        "issue_codes": sorted(set(issue_codes)),
        "warnings": sorted(set(warnings)),
    }


def build_rollback_preview(run_id: str, item_ids: list[str] | None = None) -> dict:
    run = get_run(run_id)
    run_items = get_run_items(run_id, reverse=True)
    selected = _selected_rollback_items(run_items, item_ids)
    if not selected:
        if any(item.rollback_status == str(RunItemState.ROLLED_BACK) for item in run_items):
            raise AppError(ROLLBACK_ALREADY_COMPLETED, 409)
        raise AppError(ROLLBACK_NOT_AVAILABLE, 409)

    items = [_preview_item(item) for item in selected]
    blocking_items = sum(1 for item in items if item["blocking"])
    warning_items = sum(1 for item in items if item["warnings"])
    missing_items = sum(
        1
        for item in items
        if item["current_path_status"] == "missing"
        or ROLLBACK_SOURCE_MISSING in item["issue_codes"]
        or QUARANTINE_FILE_MISSING in item["issue_codes"]
    )
    conflict_items = sum(1 for item in items if ROLLBACK_TARGET_EXISTS in item["issue_codes"])
    return {
        "run_id": run.run_id,
        "ok_to_rollback": bool(items) and blocking_items == 0,
        "summary": {
            "total_items": len(items),
            "rollbackable_items": sum(1 for item in items if item["rollback_action"] != "skip"),
            "blocking_items": blocking_items,
            "warning_items": warning_items,
            "missing_items": missing_items,
            "conflict_items": conflict_items,
        },
        "items": items,
    }


def export_run_json(run_id: str) -> dict:
    detail = build_run_detail(run_id)
    return {
        "run": {
            "run_id": detail["run_id"],
            "created_at": detail["created_at"],
            "completed_at": detail["completed_at"],
            "state": detail["state"],
            "root_dir": detail["root_dir"],
            "plan_id": detail["plan_id"],
            "plan_hash": detail["plan_hash"],
            "ruleset_hash": detail["ruleset_hash"],
        },
        "summary": {
            "selected_count": detail["selected_count"],
            "success_count": detail["success_count"],
            "failed_count": detail["failed_count"],
            "rollback_state": detail["rollback_state"],
            "rollback_available": detail["rollback_available"],
        },
        "items": detail["items"],
    }


def export_run_csv(run_id: str) -> str:
    detail = build_run_detail(run_id)
    output = io.StringIO()
    fields = [
        "run_id",
        "item_id",
        "operation",
        "status",
        "source_name",
        "target_name",
        "source_rel_path",
        "target_rel_path",
        "media_code",
        "sidecar_type",
        "issue_codes",
        "message_code",
        "rollback_status",
        "rollback_error_code",
        "size",
        "manual_edited",
        "llm_accepted",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in detail["items"]:
        writer.writerow(
            safe_csv_row({
                "run_id": detail["run_id"],
                "item_id": item["item_id"],
                "operation": item["operation"],
                "status": item["status"],
                "source_name": item["source_name"],
                "target_name": item["target_name"],
                "source_rel_path": item["source_rel_path"],
                "target_rel_path": item["target_rel_path"],
                "media_code": item["media_code"],
                "sidecar_type": item["sidecar_type"] or "",
                "issue_codes": ";".join(item["issue_codes"]),
                "message_code": item["message_code"],
                "rollback_status": item["rollback_status"],
                "rollback_error_code": item["rollback_error_code"],
                "size": item["size"],
                "manual_edited": str(item["manual_edited"]).lower(),
                "llm_accepted": str(item["llm_accepted"]).lower(),
            })
        )
    return output.getvalue()
