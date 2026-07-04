from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.enums import RunItemState, RunState
from avcleaner.models import PlanExecuteRequest, PlanRequest, ScanRequest
from avcleaner.executor import execute_plan_by_id
from avcleaner.planner import create_plan
from avcleaner.repository import create_run, create_scan, get_run, get_run_items, mark_interrupted_runs
from avcleaner.scanner import scan_files
from avcleaner.models import ExecutionRun


def plan_for(root: Path):
    scan = create_scan(ScanRequest(root_path=str(root)), scan_files(ScanRequest(root_path=str(root))))
    return create_plan(PlanRequest(scan_id=scan.scan_id))


def test_execute_writes_run_items(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = plan_for(tmp_path)

    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
    )

    items = get_run_items(response.run_id)
    assert items[0].state == RunItemState.RENAMED
    assert get_run(response.run_id).state == RunState.SUCCESS


def test_case_only_rename_uses_two_step(tmp_path: Path) -> None:
    make_file(tmp_path, "abp-123.mp4")
    plan = plan_for(tmp_path)
    item = plan.items[0]

    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[item.id], confirm=True, plan_hash=plan.plan_hash),
    )

    run_item = get_run_items(response.run_id)[0]
    assert run_item.temp_path
    assert (tmp_path / "ABP-123.mp4").exists()


def test_plan_hash_mismatch_blocks_execution(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = plan_for(tmp_path)

    try:
        execute_plan_by_id(plan.plan_id, PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash="bad"))
    except Exception as exc:
        assert "plan_hash_mismatch" in str(exc)
    else:
        raise AssertionError("hash mismatch should fail")


def test_source_changed_before_execute_blocks_by_hash(tmp_path: Path) -> None:
    source = make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = plan_for(tmp_path)
    source.write_bytes(b"changed")

    try:
        execute_plan_by_id(
            plan.plan_id,
            PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
        )
    except Exception as exc:
        assert "plan_hash_mismatch" in str(exc)
    else:
        raise AssertionError("changed source should stale the plan")


def test_startup_recovery_marks_running_runs_interrupted() -> None:
    run = create_run(ExecutionRun(run_id="run_recovery", state=RunState.RUNNING, summary={}))

    count = mark_interrupted_runs()

    assert count == 1
    assert get_run(run.run_id).state == RunState.INTERRUPTED
