from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.models import PlanRequest, ScanItem
from avcleaner.planner import create_plan


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
INDEX_HTML = ROOT / "avcleaner" / "templates" / "index.html"


def test_quarantine_reason_mapping_exists_and_keeps_raw_code_inspectable() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert '"download_residue_or_shortcut"' in text
    assert "下载残留或快捷方式" in text
    assert "quarantineReasonNode" in text
    assert "raw_code" in text
    assert "title =" in text or ".title =" in text


def test_quarantine_page_documents_non_permanent_delete() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")

    assert "隔离不是永久删除" in text
    assert "回滚恢复" in text


def test_backend_quarantine_rule_for_download_residue_is_unchanged(tmp_path: Path) -> None:
    source = make_file(tmp_path, "movie.torrent", b"torrent")
    item = ScanItem(
        id="item-1",
        path=str(source),
        relative_path=source.name,
        name=source.name,
        stem=source.stem,
        extension=source.suffix,
        size=source.stat().st_size,
        mtime=source.stat().st_mtime,
        kind="junk",
    )

    plan = create_plan(PlanRequest(root_path=str(tmp_path), files=[item]))

    assert plan.items[0].action == "quarantine"
    assert plan.items[0].reason == "download_residue_or_shortcut"


def test_large_xltd_warning_is_present_without_changing_rules() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "isLargeThunderTempFile" in text
    assert ".xltd" in text
    assert "大文件隔离可能耗时" in text
