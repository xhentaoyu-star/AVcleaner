from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.database import connect
from avcleaner.models import PlanExecuteRequest, PlanRequest, ScanRequest
from avcleaner.executor import execute_plan_by_id
from avcleaner.planner import create_plan
from avcleaner.repository import create_scan
from avcleaner.scanner import scan_files
from avcleaner.settings_store import get_settings, put_settings


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


def test_scanner_ignores_quarantine_directory(tmp_path: Path) -> None:
    q = tmp_path / ".avcleaner_quarantine" / "run" / "ad.url"
    q.parent.mkdir(parents=True)
    q.write_bytes(b"junk")
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))

    assert all(".avcleaner_quarantine" not in item.relative_path for item in scan.files)
