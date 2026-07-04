from __future__ import annotations

from pathlib import Path

from avcleaner.executor import execute_plan, rollback_run
from avcleaner.models import ExecuteRequest, PlanRequest, ScanRequest
from avcleaner.rules import build_plan
from avcleaner.scanner import scan_files
from avcleaner.validator import validate_target_name


def test_validate_target_name_blocks_windows_unsafe_names() -> None:
    assert "包含 Windows 非法字符" in validate_target_name("ABP:123.mp4", ".mp4")
    assert "文件名是 Windows 保留设备名" in validate_target_name("CON.mp4", ".mp4")
    assert "扩展名被修改" in validate_target_name("ABP-123.mkv", ".mp4")


def test_execute_requires_confirmation(tmp_path: Path) -> None:
    video = tmp_path / "hhd800.com@ABP-123.mp4"
    video.write_bytes(b"video")
    scan = scan_files(ScanRequest(root_path=str(tmp_path)))
    plan = build_plan(PlanRequest(root_path=scan.root_path, files=scan.files))

    try:
        execute_plan(ExecuteRequest(root_path=scan.root_path, items=plan.items, confirm=False))
    except ValueError as exc:
        assert "确认" in str(exc)
    else:
        raise AssertionError("execution without confirmation should fail")


def test_execute_and_rollback_rename_and_quarantine(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AVCLEANER_DATA_DIR", str(tmp_path / "state"))
    video = tmp_path / "hhd800.com@ABP-123.mp4"
    junk = tmp_path / "ad.url"
    video.write_bytes(b"video")
    junk.write_text("[InternetShortcut]", encoding="utf-8")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))
    plan = build_plan(PlanRequest(root_path=scan.root_path, files=scan.files))
    result = execute_plan(ExecuteRequest(root_path=scan.root_path, items=plan.items, confirm=True))

    assert (tmp_path / "ABP-123.mp4").exists()
    assert not video.exists()
    assert not junk.exists()
    assert any(op.action == "quarantine" and op.status == "OK" for op in result.operations)

    rollback = rollback_run(result.run_id)
    assert any(op.status == "OK" for op in rollback.operations)
    assert video.exists()
    assert junk.exists()

