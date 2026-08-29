from __future__ import annotations

import shutil
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


def test_rollback_continues_after_one_item_move_fails(tmp_path: Path, monkeypatch) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4", b"first")
    make_file(tmp_path, "hhd800.com@IPX-456.mp4", b"second")
    plan = plan_for(tmp_path)
    run = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(
            selected_item_ids=[item.id for item in plan.items],
            confirm=True,
            plan_hash=plan.plan_hash,
        ),
    )
    real_move = shutil.move
    move_calls = 0

    def fail_first_move(source: str, target: str):
        nonlocal move_calls
        move_calls += 1
        if move_calls == 1:
            raise OSError("simulated rollback move failure")
        return real_move(source, target)

    monkeypatch.setattr("avcleaner.executor.shutil.move", fail_first_move)

    rollback = rollback_run(run.run_id)

    assert rollback.state == RunState.ROLLBACK_PARTIAL
    assert {item.state for item in rollback.items} == {RunItemState.ROLLED_BACK, RunItemState.ROLLBACK_FAILED}
    assert move_calls == 2


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


def test_each_item_is_revalidated_immediately_before_execution(tmp_path: Path, monkeypatch) -> None:
    first_source = make_file(tmp_path, "hhd800.com@ABP-123.mp4", b"first")
    second_source = make_file(tmp_path, "hhd800.com@IPX-456.mp4", b"second")
    plan = plan_for(tmp_path)
    by_name = {item.original_name: item for item in plan.items}
    first_item = by_name[first_source.name]
    second_item = by_name[second_source.name]
    original_rename = Path.rename

    def rename_then_change_next(path: Path, target: Path):
        result = original_rename(path, target)
        if path == first_source:
            second_source.write_bytes(b"changed after batch validation")
        return result

    monkeypatch.setattr(Path, "rename", rename_then_change_next)

    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(
            selected_item_ids=[first_item.id, second_item.id],
            confirm=True,
            plan_hash=plan.plan_hash,
        ),
    )
    run_items = {item.plan_item_id: item for item in response.items}

    assert run_items[first_item.id].state == RunItemState.RENAMED
    assert run_items[second_item.id].state == RunItemState.FAILED
    assert run_items[second_item.id].issue_code == IssueCode.SOURCE_CHANGED
    assert second_source.read_bytes() == b"changed after batch validation"
    assert not (tmp_path / "IPX-456.mp4").exists()


def test_quarantine_rejects_symlink_swapped_outside_scan_root(tmp_path: Path, monkeypatch) -> None:
    probe_target = tmp_path / "probe-target"
    probe_target.write_text("probe", encoding="utf-8")
    probe_link = tmp_path / "probe-link"
    try:
        probe_link.symlink_to(probe_target)
    except OSError:
        pytest.skip("symbolic links are unavailable on this Windows host")
    probe_link.unlink()

    first_source = make_file(tmp_path, "hhd800.com@ABP-123.mp4", b"first")
    quarantine_source = make_file(tmp_path, "z-ad.url", b"shortcut")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_bytes(b"outside data")
    plan = plan_for(tmp_path)
    by_name = {item.original_name: item for item in plan.items}
    first_item = by_name[first_source.name]
    quarantine_item = by_name[quarantine_source.name]
    original_rename = Path.rename

    def rename_then_swap_link(path: Path, target: Path):
        result = original_rename(path, target)
        if path == first_source:
            quarantine_source.unlink()
            quarantine_source.symlink_to(outside)
        return result

    monkeypatch.setattr(Path, "rename", rename_then_swap_link)

    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(
            selected_item_ids=[first_item.id, quarantine_item.id],
            confirm=True,
            plan_hash=plan.plan_hash,
        ),
    )
    run_items = {item.plan_item_id: item for item in response.items}

    assert run_items[quarantine_item.id].state == RunItemState.FAILED
    assert run_items[quarantine_item.id].issue_code == IssueCode.PATH_ESCAPE
    assert outside.read_bytes() == b"outside data"
    outside.unlink()


def test_startup_recovery_marks_running_runs_interrupted() -> None:
    run = create_run(ExecutionRun(run_id="run_recovery", state=RunState.RUNNING, summary={}))

    count = mark_interrupted_runs()

    assert count == 1
    assert get_run(run.run_id).state == RunState.INTERRUPTED
