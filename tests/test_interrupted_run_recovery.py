from __future__ import annotations

import json
from pathlib import Path

import pytest

from avcleaner.database import connect
from avcleaner.enums import Operation, RunItemState, RunState
from avcleaner.executor import rollback_run
from avcleaner.fingerprint import snapshot_for_path
from avcleaner.models import ExecutionItem, ExecutionRun, QuarantineManifest
from avcleaner.repository import (
    create_run,
    get_run,
    get_run_items,
    mark_interrupted_runs,
    save_quarantine_manifest,
    update_quarantine_manifest_restore_copy_temp_path,
    update_quarantine_manifest_restore_copy_temp_owned,
    upsert_run_item,
)


def test_mark_interrupted_runs_fails_pending_items_and_refreshes_summary() -> None:
    run = create_run(ExecutionRun(run_id="run_recovery_contract", state=RunState.RUNNING, summary={}))
    upsert_run_item(
        ExecutionItem(
            id="runitem_done",
            run_id=run.run_id,
            plan_item_id="item_done",
            operation=Operation.RENAME,
            state=RunItemState.RENAMED,
            source_path="L:/source-a.mp4",
            target_path="L:/target-a.mp4",
        )
    )
    upsert_run_item(
        ExecutionItem(
            id="runitem_pending",
            run_id=run.run_id,
            plan_item_id="item_pending",
            operation=Operation.QUARANTINE,
            state=RunItemState.PENDING,
            source_path="L:/source-b.xltd",
            target_path="L:/source-b.xltd",
        )
    )

    assert mark_interrupted_runs() == 1

    recovered = get_run(run.run_id)
    items = {item.id: item for item in get_run_items(run.run_id)}
    assert recovered.state == RunState.INTERRUPTED
    assert recovered.completed_at
    assert recovered.rollback_available is True
    assert recovered.summary == {"failed": 1, "renamed": 1}
    assert items["runitem_pending"].state == RunItemState.FAILED
    assert items["runitem_pending"].message == "operation_interrupted"
    assert items["runitem_pending"].issue_code == "operation_interrupted"


def test_mark_interrupted_runs_recovers_journaled_quarantine_for_rollback(tmp_path: Path) -> None:
    source = tmp_path / "source" / "ad.url"
    target = tmp_path / "quarantine" / "run_recovery_quarantine" / "ad.url"
    source.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    source.write_bytes(b"important")
    snapshot = source.stat()
    run = create_run(ExecutionRun(run_id="run_recovery_quarantine", state=RunState.RUNNING, summary={}))
    upsert_run_item(
        ExecutionItem(
            id="runitem_pending_quarantine",
            run_id=run.run_id,
            plan_item_id="item_pending_quarantine",
            operation=Operation.QUARANTINE,
            state=RunItemState.PENDING,
            source_path=str(source),
            target_path="",
        )
    )
    save_quarantine_manifest(
        QuarantineManifest(
            run_id=run.run_id,
            item_id="item_pending_quarantine",
            original_abs_path=str(source),
            original_rel_path=source.name,
            quarantine_abs_path=str(target),
            size=snapshot.st_size,
            created_ns=snapshot.st_ctime_ns,
            modified_ns=snapshot.st_mtime_ns,
            reason="download_residue_or_shortcut",
            restore_status="pending",
        )
    )
    source.rename(target)

    assert mark_interrupted_runs() == 1

    recovered = get_run(run.run_id)
    recovered_item = get_run_items(run.run_id)[0]
    assert recovered.state == RunState.INTERRUPTED
    assert recovered.rollback_available is True
    assert recovered.summary == {"quarantined": 1}
    assert recovered_item.state == RunItemState.QUARANTINED
    assert recovered_item.target_path == str(target)
    with connect() as conn:
        manifest_row = conn.execute(
            "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
            (run.run_id,),
        ).fetchone()
    assert manifest_row["restore_status"] == "available"
    assert json.loads(manifest_row["manifest_json"])["restore_status"] == "available"

    rollback = rollback_run(run.run_id)

    assert rollback.state == RunState.ROLLED_BACK
    assert source.read_bytes() == b"important"
    assert not target.exists()


def test_mark_interrupted_runs_removes_journaled_partial_copy(tmp_path: Path) -> None:
    source = tmp_path / "source" / "ad.url"
    target = tmp_path / "quarantine" / "run_partial_copy" / "ad.url"
    copy_temp = target.with_name(f".{target.name}.avcleaner-copy.tmp")
    source.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    source.write_bytes(b"important")
    copy_temp.write_bytes(b"partial copy")
    snapshot = snapshot_for_path(source)
    run = create_run(ExecutionRun(run_id="run_partial_copy", state=RunState.RUNNING, summary={}))
    upsert_run_item(
        ExecutionItem(
            id="runitem_partial_copy",
            run_id=run.run_id,
            plan_item_id="item_partial_copy",
            operation=Operation.QUARANTINE,
            state=RunItemState.PENDING,
            source_path=str(source),
            target_path="",
            snapshot=snapshot,
        )
    )
    save_quarantine_manifest(
        QuarantineManifest(
            run_id=run.run_id,
            item_id="item_partial_copy",
            original_abs_path=str(source),
            original_rel_path=source.name,
            quarantine_abs_path=str(target),
            copy_temp_abs_path=str(copy_temp),
            copy_temp_owned=True,
            size=snapshot.size,
            created_ns=snapshot.created_ns,
            modified_ns=snapshot.modified_ns,
            reason="download_residue_or_shortcut",
            restore_status="pending",
        )
    )

    assert mark_interrupted_runs() == 1

    recovered_item = get_run_items(run.run_id)[0]
    assert source.read_bytes() == b"important"
    assert not copy_temp.exists()
    assert not target.exists()
    assert recovered_item.state == RunItemState.FAILED
    assert recovered_item.issue_code == "operation_interrupted"
    with connect() as conn:
        manifest_row = conn.execute(
            "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
            (run.run_id,),
        ).fetchone()
    assert manifest_row["restore_status"] == "missing"
    assert json.loads(manifest_row["manifest_json"])["copy_temp_abs_path"] == str(copy_temp)


def test_mark_interrupted_runs_preserves_unowned_preexisting_copy_temp(tmp_path: Path) -> None:
    source = tmp_path / "source" / "ad.url"
    target = tmp_path / "quarantine" / "run_preexisting_copy" / "ad.url"
    copy_temp = target.with_name(f".{target.name}.avcleaner-copy.tmp")
    source.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    source.write_bytes(b"important")
    copy_temp.write_bytes(b"user-owned preexisting file")
    snapshot = snapshot_for_path(source)
    run = create_run(ExecutionRun(run_id="run_preexisting_copy", state=RunState.RUNNING, summary={}))
    upsert_run_item(
        ExecutionItem(
            id="runitem_preexisting_copy",
            run_id=run.run_id,
            plan_item_id="item_preexisting_copy",
            operation=Operation.QUARANTINE,
            state=RunItemState.PENDING,
            source_path=str(source),
            target_path="",
            snapshot=snapshot,
        )
    )
    save_quarantine_manifest(
        QuarantineManifest(
            run_id=run.run_id,
            item_id="item_preexisting_copy",
            original_abs_path=str(source),
            original_rel_path=source.name,
            quarantine_abs_path=str(target),
            copy_temp_abs_path=str(copy_temp),
            copy_temp_owned=False,
            size=snapshot.size,
            created_ns=snapshot.created_ns,
            modified_ns=snapshot.modified_ns,
            reason="download_residue_or_shortcut",
            restore_status="pending",
        )
    )

    assert mark_interrupted_runs() == 1

    assert copy_temp.read_bytes() == b"user-owned preexisting file"
    assert source.read_bytes() == b"important"
    assert not target.exists()


def _create_interrupted_quarantine_rollback(tmp_path: Path, suffix: str):
    original = tmp_path / "source" / f"{suffix}.url"
    quarantined = tmp_path / "quarantine" / f"run_original_{suffix}" / f"{suffix}.url"
    original.parent.mkdir(parents=True)
    quarantined.parent.mkdir(parents=True)
    original.write_bytes(b"important")
    snapshot = snapshot_for_path(original)
    original.rename(quarantined)
    source_run = create_run(
        ExecutionRun(
            run_id=f"run_original_{suffix}",
            state=RunState.SUCCESS,
            summary={"quarantined": 1},
            rollback_available=True,
        )
    )
    source_item = upsert_run_item(
        ExecutionItem(
            id=f"runitem_original_{suffix}",
            run_id=source_run.run_id,
            plan_item_id=f"item_original_{suffix}",
            operation=Operation.QUARANTINE,
            state=RunItemState.QUARANTINED,
            source_path=str(original),
            target_path=str(quarantined),
            snapshot=snapshot,
        )
    )
    save_quarantine_manifest(
        QuarantineManifest(
            run_id=source_run.run_id,
            item_id=source_item.plan_item_id,
            original_abs_path=str(original),
            original_rel_path=original.name,
            quarantine_abs_path=str(quarantined),
            size=snapshot.size,
            created_ns=snapshot.created_ns,
            modified_ns=snapshot.modified_ns,
            reason="download_residue_or_shortcut",
            restore_status="available",
        )
    )
    rollback_run_record = create_run(
        ExecutionRun(
            run_id=f"run_interrupted_rollback_{suffix}",
            plan_id=source_run.run_id,
            state=RunState.ROLLBACK_RUNNING,
            summary={},
        )
    )
    upsert_run_item(
        ExecutionItem(
            id=f"runitem_interrupted_rollback_{suffix}",
            run_id=rollback_run_record.run_id,
            plan_item_id=source_item.plan_item_id,
            operation=Operation.QUARANTINE,
            state=RunItemState.PENDING,
            source_path=str(quarantined),
            target_path=str(original),
            snapshot=snapshot,
        )
    )
    return source_run, rollback_run_record, original, quarantined


@pytest.mark.parametrize(
    ("disk_state", "expected_error", "expected_manifest_status"),
    [
        ("source_only", "operation_interrupted", "restore_failed"),
        ("changed_source", "rollback_file_changed", "conflict"),
        ("both", "rollback_target_exists", "conflict"),
        ("neither", "quarantine_file_missing", "missing"),
        ("changed_target", "rollback_file_changed", "conflict"),
    ],
)
def test_mark_interrupted_runs_records_rollback_conflicts_without_guessing(
    tmp_path: Path,
    disk_state: str,
    expected_error: str,
    expected_manifest_status: str,
) -> None:
    source_run, rollback_run_record, original, quarantined = _create_interrupted_quarantine_rollback(
        tmp_path,
        disk_state,
    )
    if disk_state == "both":
        original.write_bytes(b"conflicting file")
    elif disk_state == "changed_source":
        quarantined.write_bytes(b"changed in quarantine")
    elif disk_state == "neither":
        quarantined.unlink()
    elif disk_state == "changed_target":
        quarantined.rename(original)
        original.write_bytes(b"changed after restore")

    assert mark_interrupted_runs() == 1

    recovered_rollback = get_run(rollback_run_record.run_id)
    recovered_rollback_item = get_run_items(rollback_run_record.run_id)[0]
    recovered_source = get_run(source_run.run_id)
    recovered_source_item = get_run_items(source_run.run_id)[0]
    assert recovered_rollback.state == RunState.INTERRUPTED
    assert recovered_rollback.summary == {"rollback_failed": 1}
    assert recovered_rollback_item.state == RunItemState.ROLLBACK_FAILED
    assert recovered_rollback_item.rollback_error_code == expected_error
    assert recovered_source.state == RunState.SUCCESS
    assert recovered_source.rollback_available is True
    assert recovered_source_item.rollback_status == str(RunItemState.ROLLBACK_FAILED)
    assert recovered_source_item.rollback_error_code == expected_error
    with connect() as conn:
        manifest_row = conn.execute(
            "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
            (source_run.run_id,),
        ).fetchone()
    assert manifest_row["restore_status"] == expected_manifest_status
    assert json.loads(manifest_row["manifest_json"])["restore_status"] == expected_manifest_status

    if disk_state == "source_only":
        retry = rollback_run(source_run.run_id)
        assert retry.state == RunState.ROLLED_BACK
        assert original.read_bytes() == b"important"
        assert not quarantined.exists()


def test_mark_interrupted_runs_removes_journaled_partial_restore_copy(tmp_path: Path) -> None:
    source_run, rollback_run_record, original, quarantined = _create_interrupted_quarantine_rollback(
        tmp_path,
        "partial_restore",
    )
    restore_copy_temp = original.with_name(f".{original.name}.avcleaner-copy.tmp")
    restore_copy_temp.write_bytes(b"partial restore")
    update_quarantine_manifest_restore_copy_temp_path(
        source_run.run_id,
        "item_original_partial_restore",
        str(restore_copy_temp),
    )
    update_quarantine_manifest_restore_copy_temp_owned(
        source_run.run_id,
        "item_original_partial_restore",
    )

    assert mark_interrupted_runs() == 1

    recovered_rollback_item = get_run_items(rollback_run_record.run_id)[0]
    recovered_source_item = get_run_items(source_run.run_id)[0]
    assert not restore_copy_temp.exists()
    assert quarantined.read_bytes() == b"important"
    assert not original.exists()
    assert recovered_rollback_item.state == RunItemState.ROLLBACK_FAILED
    assert recovered_rollback_item.rollback_error_code == "operation_interrupted"
    assert recovered_source_item.rollback_status == str(RunItemState.ROLLBACK_FAILED)
    with connect() as conn:
        manifest_row = conn.execute(
            "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
            (source_run.run_id,),
        ).fetchone()
    manifest_payload = json.loads(manifest_row["manifest_json"])
    assert manifest_row["restore_status"] == "restore_failed"
    assert manifest_payload["restore_copy_temp_abs_path"] == str(restore_copy_temp)


def test_mark_interrupted_runs_preserves_unowned_preexisting_restore_temp(tmp_path: Path) -> None:
    source_run, rollback_run_record, original, quarantined = _create_interrupted_quarantine_rollback(
        tmp_path,
        "preexisting_restore",
    )
    restore_copy_temp = original.with_name(f".{original.name}.avcleaner-copy.tmp")
    restore_copy_temp.write_bytes(b"user-owned preexisting file")
    update_quarantine_manifest_restore_copy_temp_path(
        source_run.run_id,
        "item_original_preexisting_restore",
        str(restore_copy_temp),
    )

    assert mark_interrupted_runs() == 1

    recovered_rollback_item = get_run_items(rollback_run_record.run_id)[0]
    assert restore_copy_temp.read_bytes() == b"user-owned preexisting file"
    assert quarantined.read_bytes() == b"important"
    assert not original.exists()
    assert recovered_rollback_item.state == RunItemState.ROLLBACK_FAILED
    assert recovered_rollback_item.rollback_error_code == "operation_interrupted"


def test_mark_interrupted_runs_recovers_completed_quarantine_rollback(tmp_path: Path) -> None:
    original = tmp_path / "source" / "ad.url"
    quarantined = tmp_path / "quarantine" / "run_original" / "ad.url"
    original.parent.mkdir(parents=True)
    quarantined.parent.mkdir(parents=True)
    original.write_bytes(b"important")
    snapshot = snapshot_for_path(original)
    original.rename(quarantined)

    source_run = create_run(
        ExecutionRun(
            run_id="run_original",
            state=RunState.SUCCESS,
            summary={"quarantined": 1},
            rollback_available=True,
        )
    )
    source_item = upsert_run_item(
        ExecutionItem(
            id="runitem_original_quarantine",
            run_id=source_run.run_id,
            plan_item_id="item_original_quarantine",
            operation=Operation.QUARANTINE,
            state=RunItemState.QUARANTINED,
            source_path=str(original),
            target_path=str(quarantined),
            snapshot=snapshot,
        )
    )
    save_quarantine_manifest(
        QuarantineManifest(
            run_id=source_run.run_id,
            item_id=source_item.plan_item_id,
            original_abs_path=str(original),
            original_rel_path=original.name,
            quarantine_abs_path=str(quarantined),
            size=snapshot.size,
            created_ns=snapshot.created_ns,
            modified_ns=snapshot.modified_ns,
            reason="download_residue_or_shortcut",
            restore_status="available",
        )
    )

    rollback_run_record = create_run(
        ExecutionRun(
            run_id="run_interrupted_rollback",
            plan_id=source_run.run_id,
            state=RunState.ROLLBACK_RUNNING,
            summary={},
        )
    )
    upsert_run_item(
        ExecutionItem(
            id="runitem_interrupted_rollback",
            run_id=rollback_run_record.run_id,
            plan_item_id=source_item.plan_item_id,
            operation=Operation.QUARANTINE,
            state=RunItemState.PENDING,
            source_path=str(quarantined),
            target_path=str(original),
            snapshot=snapshot,
        )
    )

    quarantined.rename(original)

    assert mark_interrupted_runs() == 1

    recovered_rollback = get_run(rollback_run_record.run_id)
    recovered_rollback_item = get_run_items(rollback_run_record.run_id)[0]
    recovered_source = get_run(source_run.run_id)
    recovered_source_item = get_run_items(source_run.run_id)[0]
    assert recovered_rollback.state == RunState.ROLLED_BACK
    assert recovered_rollback.summary == {"rolled_back": 1}
    assert recovered_rollback_item.state == RunItemState.ROLLED_BACK
    assert recovered_rollback_item.message == "rollback_recovered"
    assert recovered_source.state == RunState.ROLLED_BACK
    assert recovered_source.rollback_available is False
    assert recovered_source_item.rollback_status == str(RunItemState.ROLLED_BACK)
    assert recovered_source_item.rollback_error_code == ""
    with connect() as conn:
        manifest_row = conn.execute(
            "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
            (source_run.run_id,),
        ).fetchone()
    assert manifest_row["restore_status"] == "restored"
    assert json.loads(manifest_row["manifest_json"])["restore_status"] == "restored"
    assert original.read_bytes() == b"important"
    assert not quarantined.exists()
