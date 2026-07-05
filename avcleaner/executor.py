from __future__ import annotations

import shutil
import uuid
import os
from pathlib import Path

from .enums import IssueCode, Operation, PlanState, RunItemState, RunState
from .errors import AppError
from .models import ExecuteRequest, ExecuteResponse, ExecutionItem, ExecutionRun, OperationRecord, PlanExecuteRequest
from .planner import validate_stored_plan
from .quarantine import quarantine_item
from .recovery import ROLLBACK_TARGET_EXISTS, build_rollback_preview
from .repository import (
    create_run,
    get_plan,
    get_run_items,
    new_id,
    summarize_item_states,
    update_run_item_rollback_status,
    update_plan_state,
    update_run_state,
    upsert_run_item,
)
from .validators import has_blocking_issues


def _operation_record(item: ExecutionItem) -> OperationRecord:
    return OperationRecord(
        run_id=item.run_id,
        timestamp=item.updated_at,
        action=str(item.operation),
        source_path=item.source_path,
        target_path=item.target_path,
        status=str(item.state),
        message=item.message,
        size=item.snapshot.size if item.snapshot else 0,
        mtime=0,
    )


def execute_plan_by_id(plan_id: str, request: PlanExecuteRequest) -> ExecuteResponse:
    if not request.confirm:
        raise AppError("confirm_required", 400)
    original = get_plan(plan_id)
    if request.plan_hash != original.plan_hash:
        raise AppError(IssueCode.PLAN_HASH_MISMATCH, 409)

    validated = validate_stored_plan(plan_id)
    if validated.plan_hash != request.plan_hash:
        raise AppError(IssueCode.PLAN_HASH_MISMATCH, 409)

    known_ids = {item.id for item in validated.items}
    requested_ids = set(request.selected_item_ids)
    unknown_ids = requested_ids - known_ids
    if unknown_ids:
        raise AppError(IssueCode.UNKNOWN_SELECTED_ITEM_IDS, 400)
    if not requested_ids:
        raise AppError(IssueCode.NO_SELECTED_ITEMS, 400)

    selected = [item for item in validated.items if item.id in requested_ids]
    if any(has_blocking_issues(item) for item in selected):
        raise AppError(IssueCode.BLOCKING_ITEM_SELECTED, 400)
    run_id = new_id("run")
    run = create_run(
        ExecutionRun(
            run_id=run_id,
            plan_id=plan_id,
            plan_hash=validated.plan_hash,
            state=RunState.RUNNING,
            summary={},
        )
    )

    completed: list[ExecutionItem] = []
    for item in selected:
        run_item = ExecutionItem(
            id=new_id("runitem"),
            run_id=run_id,
            plan_item_id=item.id,
            operation=item.operation or item.action,
            state=RunItemState.PENDING,
            source_path=item.source_path,
            target_path=item.target_path,
            snapshot=item.snapshot,
        )
        run_item = upsert_run_item(run_item)
        try:
            if item.action == Operation.RENAME:
                run_item = _execute_rename_item(run_item, item)
            elif item.action == Operation.QUARANTINE:
                run_item = _execute_quarantine_item(run_item, Path(validated.root_path), item)
            else:
                run_item = upsert_run_item(run_item.model_copy(update={"state": RunItemState.SKIPPED, "message": "not_executable"}))
        except Exception:
            run_item = upsert_run_item(run_item.model_copy(update={"state": RunItemState.FAILED, "message": "operation_failed"}))
        completed.append(run_item)

    summary = summarize_item_states(completed)
    final_state = _final_run_state(completed)
    update_run_state(run_id, final_state, summary)
    if completed:
        update_plan_state(plan_id, PlanState.EXECUTED)
    return ExecuteResponse(
        run_id=run_id,
        operations=[_operation_record(item) for item in completed],
        items=completed,
        summary=summary,
        state=final_state,
    )


def _execute_rename_item(run_item: ExecutionItem, item) -> ExecutionItem:
    source = Path(os.path.abspath(item.source_path))
    target = Path(os.path.abspath(item.target_path))
    if not source.exists():
        return upsert_run_item(run_item.model_copy(update={"state": RunItemState.FAILED, "message": "source_missing", "issue_code": IssueCode.SOURCE_MISSING}))
    if target.exists() and str(source).lower() != str(target).lower():
        return upsert_run_item(run_item.model_copy(update={"state": RunItemState.FAILED, "message": "target_exists", "issue_code": IssueCode.TARGET_EXISTS}))
    target.parent.mkdir(parents=True, exist_ok=True)
    if item.requires_two_step or (str(source).lower() == str(target).lower() and str(source) != str(target)):
        temp = source.with_name(f".avcleaner_tmp_{uuid.uuid4().hex[:12]}{source.suffix}")
        if temp.exists():
            return upsert_run_item(run_item.model_copy(update={"state": RunItemState.FAILED, "message": "temp_target_exists"}))
        run_item = upsert_run_item(run_item.model_copy(update={"temp_path": str(temp)}))
        source.rename(temp)
        temp.rename(target)
    else:
        source.rename(target)
    return upsert_run_item(run_item.model_copy(update={"state": RunItemState.RENAMED, "message": "renamed", "target_path": str(target)}))


def _execute_quarantine_item(run_item: ExecutionItem, scan_root: Path, item) -> ExecutionItem:
    source = Path(item.source_path).resolve(strict=False)
    if not source.exists():
        return upsert_run_item(run_item.model_copy(update={"state": RunItemState.FAILED, "message": "source_missing", "issue_code": IssueCode.SOURCE_MISSING}))
    target, _manifest = quarantine_item(run_item.run_id, scan_root, item)
    return upsert_run_item(
        run_item.model_copy(update={"state": RunItemState.QUARANTINED, "message": "quarantined", "target_path": str(target)})
    )


def _final_run_state(items: list[ExecutionItem]) -> RunState:
    if not items:
        return RunState.FAILED
    successes = {RunItemState.RENAMED, RunItemState.QUARANTINED, RunItemState.SKIPPED}
    failed = [item for item in items if item.state == RunItemState.FAILED]
    succeeded = [item for item in items if item.state in successes]
    if failed and succeeded:
        return RunState.PARTIAL_SUCCESS
    if failed:
        return RunState.FAILED
    return RunState.SUCCESS


def rollback_run(run_id: str, item_ids: list[str] | None = None) -> ExecuteResponse:
    preview = build_rollback_preview(run_id, item_ids)
    source_items_by_id = {item.id: item for item in get_run_items(run_id, reverse=True)}
    source_items = [source_items_by_id[item["item_id"]] for item in preview["items"]]
    preview_by_id = {item["item_id"]: item for item in preview["items"]}
    rollback_id = new_id("run")
    create_run(ExecutionRun(run_id=rollback_id, state=RunState.ROLLBACK_RUNNING, summary={}, plan_id=run_id))
    completed: list[ExecutionItem] = []
    for source_item in source_items:
        preview_item = preview_by_id[source_item.id]
        rollback_item = ExecutionItem(
            id=new_id("runitem"),
            run_id=rollback_id,
            plan_item_id=source_item.plan_item_id,
            operation=source_item.operation,
            state=RunItemState.PENDING,
            source_path=source_item.target_path,
            target_path=source_item.source_path,
            snapshot=source_item.snapshot,
        )
        rollback_item = upsert_run_item(rollback_item)
        if preview_item["blocking"]:
            error_code = preview_item["issue_codes"][0] if preview_item["issue_codes"] else "rollback_blocked"
            legacy_issue_code = str(IssueCode.RESTORE_TARGET_EXISTS) if error_code == ROLLBACK_TARGET_EXISTS else error_code
            rollback_item = rollback_item.model_copy(
                update={
                    "state": RunItemState.ROLLBACK_FAILED,
                    "message": error_code,
                    "issue_code": legacy_issue_code,
                    "rollback_status": str(RunItemState.ROLLBACK_FAILED),
                    "rollback_error_code": error_code,
                }
            )
            update_run_item_rollback_status(source_item.id, str(RunItemState.ROLLBACK_FAILED), error_code)
        else:
            source = Path(source_item.target_path).resolve(strict=False)
            target = Path(source_item.source_path).resolve(strict=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            rollback_item = rollback_item.model_copy(
                update={
                    "state": RunItemState.ROLLED_BACK,
                    "message": "restored",
                    "rollback_status": str(RunItemState.ROLLED_BACK),
                    "rollback_error_code": "",
                }
            )
            update_run_item_rollback_status(source_item.id, str(RunItemState.ROLLED_BACK), "")
        completed.append(upsert_run_item(rollback_item))

    summary = summarize_item_states(completed)
    final_state = RunState.ROLLED_BACK if completed and all(item.state == RunItemState.ROLLED_BACK for item in completed) else RunState.ROLLBACK_PARTIAL
    update_run_state(rollback_id, final_state, summary)
    remaining = get_run_items(run_id)
    if remaining and all(
        item.state not in {RunItemState.RENAMED, RunItemState.QUARANTINED} or item.rollback_status == str(RunItemState.ROLLED_BACK)
        for item in remaining
    ):
        update_run_state(run_id, RunState.ROLLED_BACK)
    return ExecuteResponse(
        run_id=rollback_id,
        operations=[_operation_record(item) for item in completed],
        items=completed,
        summary=summary,
        state=final_state,
    )


def execute_plan(_request: ExecuteRequest) -> ExecuteResponse:
    raise AppError(IssueCode.LEGACY_EXECUTE_DISABLED, 410)
