from __future__ import annotations

import errno
from pathlib import Path

import pytest

from conftest import make_file

from avcleaner.database import connect
from avcleaner.models import PlanExecuteRequest, PlanRequest, ScanRequest
from avcleaner.executor import execute_plan_by_id
from avcleaner.planner import create_plan
from avcleaner.repository import create_scan
from avcleaner.scanner import scan_files
from avcleaner.settings_store import get_settings, put_settings
from avcleaner.quarantine import quarantine_item


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


def test_scanner_ignores_quarantine_directory(tmp_path: Path) -> None:
    q = tmp_path / ".avcleaner_quarantine" / "run" / "ad.url"
    q.parent.mkdir(parents=True)
    q.write_bytes(b"junk")
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))

    assert all(".avcleaner_quarantine" not in item.relative_path for item in scan.files)
