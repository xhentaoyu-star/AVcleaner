from __future__ import annotations

import errno
import json
import os
from pathlib import Path

import pytest

from conftest import make_file

from avcleaner.database import connect
from avcleaner.models import PlanExecuteRequest, PlanRequest, QuarantineManifest, ScanRequest
from avcleaner.executor import execute_plan_by_id, rollback_run
from avcleaner.planner import create_plan
from avcleaner.repository import create_scan
from avcleaner.scanner import scan_files
from avcleaner.settings_store import get_settings, put_settings
from avcleaner.quarantine import QuarantineRecoveryRequired, quarantine_item


class _ShortWriteFile:
    def __init__(self, handle) -> None:
        self._handle = handle
        self._shortened = False

    def __enter__(self):
        self._handle.__enter__()
        return self

    def __exit__(self, *args):
        return self._handle.__exit__(*args)

    def __getattr__(self, name: str):
        return getattr(self._handle, name)

    def write(self, data: bytes) -> int:
        if not self._shortened and data:
            self._shortened = True
            return self._handle.write(data[:-1])
        return self._handle.write(data)


def test_quarantine_uses_default_runtime_directory_and_manifest(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_file(source_root, "ad.url", b"[InternetShortcut]")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
    )

    run_item = response.items[0]
    assert ".avcleaner_quarantine" not in run_item.target_path
    assert str(source_root) not in run_item.target_path
    assert Path(run_item.target_path).parent.name == response.run_id
    with connect() as conn:
        row = conn.execute("SELECT * FROM quarantine_manifests WHERE run_id = ?", (response.run_id,)).fetchone()
    assert row["original_rel_path"] == "ad.url"
    assert row["restore_status"] == "available"


def test_quarantine_uses_configured_directory_and_manifest(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    quarantine_root = tmp_path / "custom-quarantine"
    put_settings(get_settings().model_copy(update={"quarantine_dir": str(quarantine_root)}))
    make_file(source_root, "ad.url", b"[InternetShortcut]")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
    )

    run_item = response.items[0]
    assert Path(run_item.target_path).is_relative_to(quarantine_root)
    assert Path(run_item.target_path).parent.name == response.run_id
    assert str(source_root) not in run_item.target_path
    with connect() as conn:
        row = conn.execute("SELECT quarantine_abs_path FROM quarantine_manifests WHERE run_id = ?", (response.run_id,)).fetchone()
    assert row["quarantine_abs_path"] == run_item.target_path


def test_quarantine_inside_scan_root_is_blocked_without_moving_source(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    quarantine_root = source_root / "custom-quarantine"
    put_settings(get_settings().model_copy(update={"quarantine_dir": str(quarantine_root)}))
    source = make_file(source_root, "ad.url", b"[InternetShortcut]")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    response = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
    )

    run_item = response.items[0]
    assert run_item.state == "failed"
    assert run_item.issue_code == "quarantine_inside_scan_root"
    assert source.read_bytes() == b"[InternetShortcut]"
    assert not quarantine_root.exists()


def test_successful_quarantine_rollback_updates_manifest_status(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source = make_file(source_root, "ad.url", b"[InternetShortcut]")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    executed = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
    )

    rollback = rollback_run(executed.run_id)

    assert rollback.state == "rolled_back"
    assert source.exists()
    with connect() as conn:
        row = conn.execute(
            "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
            (executed.run_id,),
        ).fetchone()
    assert row["restore_status"] == "restored"
    manifest_payload = json.loads(row["manifest_json"])
    assert manifest_payload["restore_status"] == "restored"
    assert manifest_payload["restore_copy_temp_abs_path"]
    assert not Path(manifest_payload["restore_copy_temp_abs_path"]).exists()


def test_failed_quarantine_rollback_manifest_status_round_trips(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    make_file(source_root, "ad.url", b"[InternetShortcut]")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    executed = execute_plan_by_id(
        plan.plan_id,
        PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
    )

    def fail_restore(*_args, **_kwargs) -> None:
        raise OSError("restore failed")

    monkeypatch.setattr("avcleaner.executor.move_file_verified", fail_restore)

    rollback_run(executed.run_id)

    with connect() as conn:
        row = conn.execute(
            "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
            (executed.run_id,),
        ).fetchone()
    payload = json.loads(row["manifest_json"])
    assert row["restore_status"] == "restore_failed"
    assert QuarantineManifest.model_validate(payload).restore_status == "restore_failed"


def test_quarantine_reports_move_progress(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    make_file(source_root, "ad.url", b"[InternetShortcut]")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    events: list[tuple[int, int]] = []

    target, _manifest = quarantine_item(
        "run_progress_contract",
        source_root,
        plan.items[0],
        str(tmp_path / "custom-quarantine"),
        progress_callback=lambda copied, total: events.append((copied, total)),
    )

    assert target.exists()
    assert events
    assert events[-1][0] == events[-1][1]
    assert events[-1][1] > 0


def test_cross_volume_quarantine_records_copy_temp_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    quarantine_root = tmp_path / "custom-quarantine"
    source = make_file(source_root, "ad.url", b"important source bytes")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    real_rename = Path.rename
    from avcleaner import quarantine as quarantine_module

    def force_cross_volume(path: Path, target: Path):
        if path == source:
            raise OSError(errno.EXDEV, "cross-volume test")
        return real_rename(path, target)

    monkeypatch.setattr(Path, "rename", force_cross_volume)

    target, _manifest = quarantine_item(
        "run_copy_temp_owned",
        source_root,
        plan.items[0],
        str(quarantine_root),
    )

    with connect() as conn:
        row = conn.execute(
            "SELECT manifest_json FROM quarantine_manifests WHERE run_id = ?",
            ("run_copy_temp_owned",),
        ).fetchone()
    payload = json.loads(row["manifest_json"])
    assert payload["copy_temp_owned"] is True
    assert payload["copy_temp_abs_path"] == str(quarantine_module.copy_temp_path_for(target))
    assert not Path(payload["copy_temp_abs_path"]).exists()


def test_quarantine_journal_is_written_before_source_move(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    source = make_file(source_root, "ad.url", b"[InternetShortcut]")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    from avcleaner import quarantine as quarantine_module

    real_move = quarantine_module.move_file_verified
    observed_statuses: list[str] = []

    def verify_journal_then_move(
        source_path: Path,
        target_path: Path,
        progress_callback=None,
        temp_created_callback=None,
    ) -> None:
        with connect() as conn:
            row = conn.execute(
                "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
                ("run_prewrite_journal",),
            ).fetchone()
        observed_statuses.append(row["restore_status"])
        manifest_payload = json.loads(row["manifest_json"])
        assert manifest_payload["restore_status"] == "pending"
        assert manifest_payload["copy_temp_abs_path"] == str(quarantine_module.copy_temp_path_for(target_path))
        assert manifest_payload["copy_temp_owned"] is False
        assert source_path.exists()
        assert not target_path.exists()
        real_move(source_path, target_path, progress_callback, temp_created_callback)

    monkeypatch.setattr(quarantine_module, "move_file_verified", verify_journal_then_move)

    target, manifest = quarantine_item(
        "run_prewrite_journal",
        source_root,
        plan.items[0],
        str(tmp_path / "custom-quarantine"),
    )

    assert observed_statuses == ["pending"]
    assert manifest.restore_status == "available"
    assert target.exists()
    assert not source.exists()


def test_move_error_after_target_creation_keeps_recovery_journal(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source = make_file(source_root, "ad.url", b"[InternetShortcut]")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    def fail_progress(_copied: int, _total: int) -> None:
        raise OSError("simulated progress failure")

    with pytest.raises(QuarantineRecoveryRequired) as exc:
        quarantine_item(
            "run_progress_recovery",
            source_root,
            plan.items[0],
            str(tmp_path / "custom-quarantine"),
            progress_callback=fail_progress,
        )

    assert exc.value.target_path.read_bytes() == b"[InternetShortcut]"
    assert not source.exists()
    with connect() as conn:
        manifest = conn.execute(
            "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
            ("run_progress_recovery",),
        ).fetchone()
    assert manifest["restore_status"] == "pending"
    assert json.loads(manifest["manifest_json"])["quarantine_abs_path"] == str(exc.value.target_path)


def test_cross_volume_quarantine_keeps_source_when_copy_is_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    quarantine_root = tmp_path / "custom-quarantine"
    source = make_file(source_root, "ad.url", b"important source bytes")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    real_rename = Path.rename
    real_open = Path.open

    def force_cross_volume(path: Path, target: Path):
        if path == source:
            raise OSError(errno.EXDEV, "cross-volume test")
        return real_rename(path, target)

    def short_write(path: Path, mode: str = "r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        if mode == "xb" and quarantine_root in path.parents:
            return _ShortWriteFile(handle)
        return handle

    monkeypatch.setattr(Path, "rename", force_cross_volume)
    monkeypatch.setattr(Path, "open", short_write)

    with pytest.raises(OSError):
        quarantine_item("run_incomplete_copy", source_root, plan.items[0], str(quarantine_root))

    assert source.read_bytes() == b"important source bytes"
    assert not any(path.is_file() for path in quarantine_root.rglob("*"))


def test_cross_volume_quarantine_keeps_source_changed_during_target_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    quarantine_root = tmp_path / "custom-quarantine"
    source = make_file(source_root, "ad.url", b"important source bytes")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    real_rename = Path.rename

    def force_cross_volume(path: Path, target: Path):
        if path == source:
            raise OSError(errno.EXDEV, "cross-volume test")
        return real_rename(path, target)

    from avcleaner import quarantine as quarantine_module

    real_hash = quarantine_module._sha256_file

    def hash_and_change_source(path: Path) -> str:
        if path.name.endswith(".avcleaner-copy.tmp"):
            source.write_bytes(source.read_bytes() + b" changed while verifying")
        return real_hash(path)

    monkeypatch.setattr(Path, "rename", force_cross_volume)
    monkeypatch.setattr(quarantine_module, "_sha256_file", hash_and_change_source)

    with pytest.raises(OSError, match="quarantine_source_changed_during_verification"):
        quarantine_item("run_changed_source", source_root, plan.items[0], str(quarantine_root))

    assert source.read_bytes().endswith(b"changed while verifying")
    assert not any(path.is_file() for path in quarantine_root.rglob("*"))


def test_cross_volume_quarantine_rehashes_source_before_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    quarantine_root = tmp_path / "custom-quarantine"
    original_bytes = b"important source bytes"
    source = make_file(source_root, "ad.url", original_bytes)
    original_stat = source.stat()
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    real_rename = Path.rename

    def force_cross_volume(path: Path, target: Path):
        if path == source:
            raise OSError(errno.EXDEV, "cross-volume test")
        return real_rename(path, target)

    from avcleaner import quarantine as quarantine_module

    real_hash = quarantine_module._sha256_file

    def hash_and_replace_source(path: Path) -> str:
        if path.name.endswith(".avcleaner-copy.tmp"):
            source.write_bytes(b"X" * len(original_bytes))
            os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        return real_hash(path)

    monkeypatch.setattr(Path, "rename", force_cross_volume)
    monkeypatch.setattr(quarantine_module, "_sha256_file", hash_and_replace_source)

    with pytest.raises(OSError, match="quarantine_source_changed_during_verification"):
        quarantine_item("run_rehash_source", source_root, plan.items[0], str(quarantine_root))

    assert source.read_bytes() == b"X" * len(original_bytes)
    assert source.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert not any(path.is_file() for path in quarantine_root.rglob("*"))


def test_cross_volume_copy_does_not_delete_preexisting_temp_path(tmp_path: Path) -> None:
    from avcleaner import quarantine as quarantine_module

    source = make_file(tmp_path / "source", "ad.url", b"source bytes")
    target = tmp_path / "quarantine" / "ad.url"
    target.parent.mkdir(parents=True)
    temp = quarantine_module.copy_temp_path_for(target)
    temp.write_bytes(b"preexisting bytes")

    with pytest.raises(FileExistsError):
        quarantine_module._copy_then_delete_verified(source, target)

    assert source.read_bytes() == b"source bytes"
    assert temp.read_bytes() == b"preexisting bytes"
    assert not target.exists()


def test_manifest_failure_restores_quarantined_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    quarantine_root = tmp_path / "custom-quarantine"
    source = make_file(source_root, "ad.url", b"recoverable source bytes")
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    def fail_manifest(_manifest) -> None:
        raise OSError("manifest write failed")

    monkeypatch.setattr("avcleaner.quarantine.save_quarantine_manifest", fail_manifest)

    with pytest.raises(OSError, match="manifest write failed"):
        quarantine_item("run_manifest_failure", source_root, plan.items[0], str(quarantine_root))

    assert source.read_bytes() == b"recoverable source bytes"
    assert not any(path.is_file() for path in quarantine_root.rglob("*"))


def test_manifest_status_and_compensation_failure_can_be_rolled_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "source"
    quarantine_root = tmp_path / "custom-quarantine"
    source = make_file(source_root, "ad.url", b"recoverable source bytes")
    put_settings(get_settings().model_copy(update={"quarantine_dir": str(quarantine_root)}))
    scan = create_scan(ScanRequest(root_path=str(source_root)), scan_files(ScanRequest(root_path=str(source_root))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    from avcleaner import quarantine as quarantine_module

    real_move = quarantine_module.move_file_verified
    move_calls = 0

    def fail_compensation(
        source_path: Path,
        target_path: Path,
        progress_callback=None,
        temp_created_callback=None,
    ) -> None:
        nonlocal move_calls
        move_calls += 1
        if move_calls == 2:
            raise OSError("simulated compensation failure")
        real_move(source_path, target_path, progress_callback, temp_created_callback)

    def fail_status_update(*_args, **_kwargs) -> None:
        raise OSError("simulated manifest status failure")

    with monkeypatch.context() as scoped:
        scoped.setattr(quarantine_module, "move_file_verified", fail_compensation)
        scoped.setattr(quarantine_module, "update_quarantine_manifest_restore_status", fail_status_update)
        executed = execute_plan_by_id(
            plan.plan_id,
            PlanExecuteRequest(selected_item_ids=[plan.items[0].id], confirm=True, plan_hash=plan.plan_hash),
        )

    run_item = executed.items[0]
    assert run_item.state == "failed"
    assert run_item.issue_code == "quarantine_recovery_required"
    assert Path(run_item.temp_path).read_bytes() == b"recoverable source bytes"
    assert not source.exists()
    with connect() as conn:
        pending_manifest = conn.execute(
            "SELECT restore_status FROM quarantine_manifests WHERE run_id = ?",
            (executed.run_id,),
        ).fetchone()
    assert pending_manifest["restore_status"] == "pending"

    rollback = rollback_run(executed.run_id)

    assert rollback.state == "rolled_back"
    assert source.read_bytes() == b"recoverable source bytes"
    with connect() as conn:
        restored_manifest = conn.execute(
            "SELECT restore_status, manifest_json FROM quarantine_manifests WHERE run_id = ?",
            (executed.run_id,),
        ).fetchone()
    assert restored_manifest["restore_status"] == "restored"
    assert QuarantineManifest.model_validate(json.loads(restored_manifest["manifest_json"])).restore_status == "restored"


def test_scanner_ignores_quarantine_directory(tmp_path: Path) -> None:
    q = tmp_path / ".avcleaner_quarantine" / "run" / "ad.url"
    q.parent.mkdir(parents=True)
    q.write_bytes(b"junk")
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))

    assert all(".avcleaner_quarantine" not in item.relative_path for item in scan.files)
