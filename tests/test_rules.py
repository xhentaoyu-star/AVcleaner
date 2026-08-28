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


def test_obvious_advertising_filenames_default_to_quarantine(tmp_path: Path) -> None:
    advertising_video = tmp_path / "18+游戏大全(996gg.cc)-七龍珠H版-三國志H版-三國群淫傳等.mp4"
    advertising_page = tmp_path / "聚 合 全 網 H 直 播.html"
    advertising_video.write_bytes(b"video")
    advertising_page.write_text("advertising", encoding="utf-8")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))
    for plan in [
        build_plan(PlanRequest(root_path=scan.root_path, files=scan.files)),
        create_plan(PlanRequest(root_path=scan.root_path, files=scan.files)),
    ]:
        by_name = {item.original_name: item for item in plan.items}
        for file in [advertising_video, advertising_page]:
            item = by_name[file.name]
            assert item.action == "quarantine"
            assert item.checked is True
            assert item.selected is True
            assert item.requires_review is False
            assert item.reason == "obvious_advertising_filename"


def test_files_inside_advertising_directory_default_to_quarantine(tmp_path: Path) -> None:
    advertising_dir = tmp_path / "IPX-633" / "宣傳文件"
    advertising_dir.mkdir(parents=True)
    advertising_files = [
        advertising_dir / "594.wmv",
        advertising_dir / "FB-559" / "FB-559.jpg",
        advertising_dir / "TY-996" / "TY-996.jpg",
        advertising_dir / "[日本同步]新片合集发布.mht",
        advertising_dir / "_1024核工厂最新地址.mht",
        advertising_dir / "avmans最新导航地址.html",
        advertising_dir / "更多精彩點擊這裡訪問.mht",
        advertising_dir / "防屏蔽二維碼，請掃描保存到你手機.png",
    ]
    for file in advertising_files:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"advertising")
    legitimate = tmp_path / "IPX-633" / "IPX-633.mp4"
    legitimate.write_bytes(b"video")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))
    plan = create_plan(PlanRequest(root_path=scan.root_path, files=scan.files))
    by_path = {item.source_rel_path: item for item in plan.items}

    for file in advertising_files:
        item = by_path[str(file.relative_to(tmp_path))]
        assert item.action == "quarantine"
        assert item.selected_default is True
        assert item.requires_review is False
        assert item.reason == "advertising_directory"
    assert by_path[str(legitimate.relative_to(tmp_path))].action == "keep"


def test_advertising_directory_bypasses_extension_filter(tmp_path: Path) -> None:
    advertising_dir = tmp_path / "IPX-633" / "宣傳文件"
    advertising_dir.mkdir(parents=True)
    advertising_files = [
        advertising_dir / "魔王之家~魔王在線防屏蔽發布器.rar",
        advertising_dir / "台湾辣妹聊天室XC25.COM.gif",
        advertising_dir / "avmans最新导航地址.chm",
    ]
    for file in advertising_files:
        file.write_bytes(b"advertising")
    unrelated_archive = tmp_path / "legitimate-backup.rar"
    unrelated_archive.write_bytes(b"backup")

    scan = scan_files(ScanRequest(root_path=str(tmp_path), extensions=[".mp4"]))
    scanned_paths = {item.relative_path for item in scan.files}
    assert scanned_paths == {str(file.relative_to(tmp_path)) for file in advertising_files}
    plan = build_plan(PlanRequest(root_path=scan.root_path, files=scan.files))
    by_path = {item.source_rel_path: item for item in plan.items}

    for file in advertising_files:
        item = by_path[str(file.relative_to(tmp_path))]
        assert item.action == "quarantine"
        assert item.selected_default is True
        assert item.reason == "advertising_directory"
    assert str(unrelated_archive.relative_to(tmp_path)) not in by_path


def test_obvious_advertising_image_defaults_to_quarantine(tmp_path: Path) -> None:
    advertising_image = tmp_path / "色中色论坛地址宣传图.jpg"
    advertising_image.write_bytes(b"advertising")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))
    plan = create_plan(PlanRequest(root_path=scan.root_path, files=scan.files))
    item = next(current for current in plan.items if current.original_name == advertising_image.name)

    assert item.action == "quarantine"
    assert item.selected_default is True
    assert item.reason == "obvious_advertising_filename"


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
