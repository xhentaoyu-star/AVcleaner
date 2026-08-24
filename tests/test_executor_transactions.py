from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_file

from avcleaner.enums import IssueCode, RunItemState, RunState
from avcleaner.errors import AppError
from avcleaner.models import PlanExecuteRequest, PlanRequest, ScanRequest
from avcleaner.executor import execute_plan_by_id, rollback_run, validate_execute_request
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


def test_locked_rename_retries_and_reports_file_in_use(tmp_path: Path, monkeypatch) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = plan_for(tmp_path)
    rename_calls = 0

    def fail_with_windows_sharing_violation(_path: Path, _target: Path):
        nonlocal rename_calls
        rename_calls += 1
        exc = PermissionError("simulated Windows sharing violation")
        exc.winerror = 32
        raise exc

    monkeypatch.setattr(Path, "rename", fail_with_windows_sharing_violation)
    monkeypatch.setattr("avcleaner.executor.RENAME_RETRY_DELAY_SECONDS", 0.0)
    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
    )

    run_item = get_run_items(response.run_id)[0]
    assert rename_calls == 3
    assert run_item.state == RunItemState.FAILED
    assert run_item.message == "file_in_use"
    assert run_item.issue_code == "file_in_use"


def test_transient_file_lock_succeeds_on_retry(tmp_path: Path, monkeypatch) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = plan_for(tmp_path)
    original_rename = Path.rename
    rename_calls = 0

    def fail_twice_then_rename(path: Path, target: Path):
        nonlocal rename_calls
        rename_calls += 1
        if rename_calls < 3:
            exc = PermissionError("simulated transient Windows sharing violation")
            exc.winerror = 32
            raise exc
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_twice_then_rename)
    monkeypatch.setattr("avcleaner.executor.RENAME_RETRY_DELAY_SECONDS", 0.0)

    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
    )

    run_item = get_run_items(response.run_id)[0]
    assert rename_calls == 3
    assert run_item.state == RunItemState.RENAMED
    assert (tmp_path / "ABP-123.mp4").exists()


def test_requires_review_quarantine_cannot_be_executed_directly(tmp_path: Path) -> None:
    residue = tmp_path / "midv-192-4k.mp4.xltd"
    with residue.open("wb") as handle:
        handle.truncate(2 * 1024 * 1024 * 1024)
    plan = plan_for(tmp_path)
    item = plan.items[0]

    assert item.requires_review is True
    with pytest.raises(AppError) as exc_info:
        validate_execute_request(
            plan.plan_id,
            PlanExecuteRequest(selected_item_ids=[item.id], confirm=True, plan_hash=plan.plan_hash),
        )

    assert exc_info.value.error_code == IssueCode.REQUIRES_REVIEW_ITEM_SELECTED


def test_case_only_rename_restores_source_when_second_step_fails(tmp_path: Path, monkeypatch) -> None:
    source = make_file(tmp_path, "abp-123.mp4")
    plan = plan_for(tmp_path)
    item = plan.items[0]
    original_rename = Path.rename
    rename_calls = 0

    def fail_target_rename_once(path: Path, target: Path):
        nonlocal rename_calls
        rename_calls += 1
        if rename_calls == 2:
            raise OSError("simulated target rename failure")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_target_rename_once)

    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[item.id], confirm=True, plan_hash=plan.plan_hash),
    )

    run_item = get_run_items(response.run_id)[0]
    assert run_item.state == RunItemState.FAILED
    assert run_item.message == "rename_failed_source_restored"
    assert source.exists()
    assert "abp-123.mp4" in {path.name for path in tmp_path.iterdir()}
    assert not list(tmp_path.glob(".avcleaner_tmp_*"))


def test_case_only_rename_persists_temp_path_for_later_rollback(tmp_path: Path, monkeypatch) -> None:
    source = make_file(tmp_path, "abp-123.mp4")
    plan = plan_for(tmp_path)
    item = plan.items[0]
    original_rename = Path.rename
    rename_calls = 0

    def fail_target_and_compensation(path: Path, target: Path):
        nonlocal rename_calls
        rename_calls += 1
        if rename_calls >= 2:
            raise OSError("simulated persistent rename failure")
        return original_rename(path, target)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "rename", fail_target_and_compensation)
        response = execute_plan_by_id(
            plan.plan_id,
            PlanExecuteRequest(selected_item_ids=[item.id], confirm=True, plan_hash=plan.plan_hash),
        )

    run_item = get_run_items(response.run_id)[0]
    assert run_item.state == RunItemState.FAILED
    assert run_item.message == "rename_recovery_required"
    assert run_item.temp_path
    assert Path(run_item.temp_path).exists()
    assert not source.exists()

    rollback = rollback_run(response.run_id)

    assert rollback.state == RunState.ROLLED_BACK
    assert source.exists()
    assert not Path(run_item.temp_path).exists()


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
