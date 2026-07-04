from __future__ import annotations

import shutil
import uuid
from collections import Counter
from pathlib import Path

from .database import operations_for_run, utc_now_iso, write_run
from .models import ExecuteRequest, ExecuteResponse, OperationRecord, PlanItem
from .paths import is_relative_to, quarantine_root, safe_relative_path
from .rules import validate_plan_items


def _record(
    run_id: str,
    action: str,
    source_path: str,
    target_path: str,
    status: str,
    message: str = "",
    size: int = 0,
    mtime: float = 0.0,
) -> OperationRecord:
    return OperationRecord(
        run_id=run_id,
        timestamp=utc_now_iso(),
        action=action,
        source_path=source_path,
        target_path=target_path,
        status=status,
        message=message,
        size=size,
        mtime=mtime,
    )


def execute_plan(request: ExecuteRequest) -> ExecuteResponse:
    if not request.confirm:
        raise ValueError("执行前必须确认")

    root = Path(request.root_path).resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise ValueError("根目录不存在")

    run_id = uuid.uuid4().hex
    items = [item for item in request.items if item.checked and item.action in {"rename", "quarantine"}]
    validate_plan_items(root, items)
    operations: list[OperationRecord] = []

    for item in items:
        if item.warnings and any(_is_blocking_warning(warning) for warning in item.warnings):
            operations.append(
                _record(run_id, item.action, item.source_path, item.target_path, "Skipped", "blocked by validation", item.size, item.mtime)
            )
            continue
        try:
            if item.action == "rename":
                operations.append(_execute_rename(run_id, root, item))
            elif item.action == "quarantine":
                operations.append(_execute_quarantine(run_id, root, item))
        except Exception:
            operations.append(
                _record(run_id, item.action, item.source_path, item.target_path, "Error", "operation failed", item.size, item.mtime)
            )

    write_run(run_id, operations)
    return ExecuteResponse(run_id=run_id, operations=operations, summary=dict(Counter(f"{op.action}:{op.status}" for op in operations)))


def _is_blocking_warning(warning: str) -> bool:
    return warning in {"路径越界", "目标文件名重复", "目标文件已存在", "目标路径过长", "包含 Windows 非法字符", "文件名为空", "扩展名被修改", "文件名是 Windows 保留设备名"}


def _execute_rename(run_id: str, root: Path, item: PlanItem) -> OperationRecord:
    source = Path(item.source_path).resolve(strict=False)
    target = Path(item.target_path).resolve(strict=False)
    if not is_relative_to(source, root) or not is_relative_to(target, root):
        return _record(run_id, "rename", str(source), str(target), "Skipped", "path outside root", item.size, item.mtime)
    if not source.exists():
        return _record(run_id, "rename", str(source), str(target), "Skipped", "source missing", item.size, item.mtime)
    if target.exists() and str(target).lower() != str(source).lower():
        return _record(run_id, "rename", str(source), str(target), "Skipped", "target exists", item.size, item.mtime)

    target.parent.mkdir(parents=True, exist_ok=True)
    if str(target).lower() == str(source).lower() and str(target) != str(source):
        temp = source.with_name(f".__avcleaner_tmp_{uuid.uuid4().hex}{source.suffix}")
        source.rename(temp)
        temp.rename(target)
    else:
        source.rename(target)
    return _record(run_id, "rename", str(source), str(target), "OK", "renamed", item.size, item.mtime)


def _execute_quarantine(run_id: str, root: Path, item: PlanItem) -> OperationRecord:
    source = Path(item.source_path).resolve(strict=False)
    if not is_relative_to(source, root):
        return _record(run_id, "quarantine", str(source), "", "Skipped", "path outside root", item.size, item.mtime)
    if not source.exists():
        return _record(run_id, "quarantine", str(source), "", "Skipped", "source missing", item.size, item.mtime)

    relative = safe_relative_path(source, root)
    target = quarantine_root() / uuid.uuid4().hex[:8] / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target = target.with_name(f"{target.stem}__duplicate_{uuid.uuid4().hex[:8]}{target.suffix}")
    shutil.move(str(source), str(target))
    return _record(run_id, "quarantine", str(source), str(target), "OK", "moved to quarantine", item.size, item.mtime)


def rollback_run(run_id: str) -> ExecuteResponse:
    source_operations = [op for op in operations_for_run(run_id) if op.status == "OK"]
    rollback_id = uuid.uuid4().hex
    operations: list[OperationRecord] = []

    for op in source_operations:
        try:
            if op.action in {"rename", "quarantine"}:
                operations.append(_rollback_move(rollback_id, op))
        except Exception:
            operations.append(
                _record(rollback_id, f"rollback:{op.action}", op.target_path, op.source_path, "Error", "rollback failed", op.size, op.mtime)
            )

    write_run(rollback_id, operations)
    return ExecuteResponse(
        run_id=rollback_id,
        operations=operations,
        summary=dict(Counter(f"{op.action}:{op.status}" for op in operations)),
    )


def _rollback_move(rollback_id: str, op: OperationRecord) -> OperationRecord:
    source = Path(op.target_path).resolve(strict=False)
    target = Path(op.source_path).resolve(strict=False)
    if not source.exists():
        return _record(rollback_id, f"rollback:{op.action}", str(source), str(target), "Skipped", "rollback source missing", op.size, op.mtime)
    if target.exists():
        return _record(rollback_id, f"rollback:{op.action}", str(source), str(target), "Skipped", "original path exists", op.size, op.mtime)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    return _record(rollback_id, f"rollback:{op.action}", str(source), str(target), "OK", "restored", op.size, op.mtime)

