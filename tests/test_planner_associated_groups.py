from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.enums import Operation
from avcleaner.models import PlanRequest, ScanRequest
from avcleaner.planner import create_plan
from avcleaner.repository import create_scan
from avcleaner.scanner import scan_files


def create_plan_for(root: Path):
    scan = create_scan(ScanRequest(root_path=str(root)), scan_files(ScanRequest(root_path=str(root))))
    return create_plan(PlanRequest(scan_id=scan.scan_id))


def test_planner_groups_video_and_sidecars_without_auto_selecting_sidecars(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path, "[ad] ABP123.chs.ass")
    make_file(tmp_path, "ABP-123.jpg")

    plan = create_plan_for(tmp_path)
    by_name = {item.original_name: item for item in plan.items}
    video = by_name["hhd800.com@ABP-123.mp4"]
    subtitle = by_name["[ad] ABP123.chs.ass"]
    image = by_name["ABP-123.jpg"]

    assert video.group_id
    assert subtitle.group_id == video.group_id
    assert image.group_id == video.group_id
    assert subtitle.sidecar_type == "subtitle"
    assert subtitle.language_suffix == "chs"
    assert subtitle.associated_media_code == "ABP-123"
    assert subtitle.action == Operation.RENAME
    assert subtitle.target_name == "ABP-123.chs.ass"
    assert subtitle.checked is False
    assert subtitle.selected_default is False
    assert image.sidecar_type == "image"
    assert image.checked is False
    assert image.selected_default is False


def test_group_id_is_stable_for_same_inputs(tmp_path: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    make_file(root, "hhd800.com@ABP-123.mp4")
    make_file(root, "[ad] ABP123.zh.srt")

    first = create_plan_for(root)
    second = create_plan_for(root)
    first_groups = sorted((item.original_name, item.group_id) for item in first.items)
    second_groups = sorted((item.original_name, item.group_id) for item in second.items)

    assert first_groups == second_groups
