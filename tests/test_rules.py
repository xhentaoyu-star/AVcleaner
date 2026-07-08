from __future__ import annotations

from pathlib import Path

from avcleaner.models import PlanRequest, ScanRequest
from avcleaner.planner import create_plan
from avcleaner.rules import build_plan, extract_media_code
from avcleaner.scanner import scan_files


def test_extract_media_code_supported_formats() -> None:
    examples = {
        "[www.abc.com]ABP-123-C.mp4": ("ABP-123", "", "-C"),
        "hhd800.com@IPX999_1080p.mp4": ("IPX-999", "", ""),
        "FC2-PPV-1234567_uncensored.mp4": ("FC2-PPV-1234567", "", "-UNCENSORED"),
        "428SUKE-095.mp4": ("428SUKE-095", "", ""),
        "014248_141.mp4": ("014248_141", "", ""),
        "HEYZO-1234.mp4": ("HEYZO-1234", "", ""),
        "SUPD-103C.mp4": ("SUPD-103", "", "-C"),
        "hhd800.com@FC2-PPV-4856696_2.mp4": ("FC2-PPV-4856696", "-2", ""),
    }
    for filename, expected in examples.items():
        code = extract_media_code(filename)
        assert code is not None
        assert (code.code, code.part_suffix, code.variant) == expected


def test_build_plan_renames_video_and_keeps_sidecar(tmp_path: Path) -> None:
    video = tmp_path / "hhd800.com@FC2-PPV-4856696_1.mp4"
    sidecar = tmp_path / "hhd800.com@FC2-PPV-4856696_1.nfo"
    video.write_bytes(b"video")
    sidecar.write_text("<xml />", encoding="utf-8")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))
    plan = build_plan(PlanRequest(root_path=scan.root_path, files=scan.files))
    by_name = {item.original_name: item for item in plan.items}

    assert by_name[video.name].action == "rename"
    assert by_name[video.name].suggested_name == "FC2-PPV-4856696-1.mp4"
    assert by_name[sidecar.name].action == "keep"


def test_junk_candidates_default_to_quarantine(tmp_path: Path) -> None:
    url = tmp_path / "最新地址.url"
    torrent = tmp_path / "movie.torrent"
    subtitle = tmp_path / "ABP-123.srt"
    empty = tmp_path / "empty.txt"
    url.write_text("[InternetShortcut]", encoding="utf-8")
    torrent.write_bytes(b"torrent")
    subtitle.write_text("1\nsubtitle", encoding="utf-8")
    empty.write_bytes(b"")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))
    plan = build_plan(PlanRequest(root_path=scan.root_path, files=scan.files))
    actions = {item.original_name: item.action for item in plan.items}

    assert actions[url.name] == "quarantine"
    assert actions[torrent.name] == "quarantine"
    assert actions[empty.name] == "quarantine"
    assert actions[subtitle.name] == "keep"


def test_large_temp_download_residue_requires_manual_selection(tmp_path: Path) -> None:
    residue = tmp_path / "midv-192-4k.mp4.xltd"
    with residue.open("wb") as handle:
        handle.truncate(2 * 1024 * 1024 * 1024)

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))
    plan = build_plan(PlanRequest(root_path=scan.root_path, files=scan.files))
    item = next(plan_item for plan_item in plan.items if plan_item.original_name == residue.name)

    assert item.action == "quarantine"
    assert item.checked is False
    assert item.selected is False
    assert item.selected_default is False
    assert item.requires_review is True
    assert "large_temp_file_requires_manual_selection" in item.warnings

    stored_style_plan = create_plan(PlanRequest(root_path=scan.root_path, files=scan.files))
    stored_style_item = next(plan_item for plan_item in stored_style_plan.items if plan_item.original_name == residue.name)
    assert stored_style_item.checked is False
    assert stored_style_item.selected is False
    assert stored_style_item.requires_review is True
    assert "large_temp_file_requires_manual_selection" in stored_style_item.review_reason_codes


def test_duplicate_targets_get_cd_suffix(tmp_path: Path) -> None:
    a = tmp_path / "abc.com@ABP-123.mp4"
    b = tmp_path / "hhd800.com@ABP-123.mp4"
    a.write_bytes(b"a")
    b.write_bytes(b"b")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))
    plan = build_plan(PlanRequest(root_path=scan.root_path, files=scan.files))
    names = sorted(item.suggested_name for item in plan.items if item.action == "rename")

    assert names == ["ABP-123-CD01.mp4", "ABP-123-CD02.mp4"]
