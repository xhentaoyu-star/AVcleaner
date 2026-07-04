from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.enums import RunItemState
from avcleaner.executor import execute_plan_by_id, rollback_run
from avcleaner.models import PlanExecuteRequest, PlanRequest, ScanRequest
from avcleaner.planner import create_plan
from avcleaner.repository import create_scan
from avcleaner.scanner import scan_files


def test_rollback_restores_rename(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    scan = create_scan(ScanRequest(root_path=str(tmp_path)), scan_files(ScanRequest(root_path=str(tmp_path))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    run = execute_plan_by_id(plan.plan_id, PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash))

    rollback = rollback_run(run.run_id)

    assert rollback.items[0].state == RunItemState.ROLLED_BACK
    assert (tmp_path / "hhd800.com@ABP-123.mp4").exists()


def test_rollback_conflict_never_overwrites(tmp_path: Path) -> None:
    original = make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    scan = create_scan(ScanRequest(root_path=str(tmp_path)), scan_files(ScanRequest(root_path=str(tmp_path))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    run = execute_plan_by_id(plan.plan_id, PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash))
    original.write_bytes(b"new file")

    rollback = rollback_run(run.run_id)

    assert rollback.items[0].state == RunItemState.ROLLBACK_FAILED
    assert rollback.items[0].issue_code == "restore_target_exists"
    assert original.read_bytes() == b"new file"
