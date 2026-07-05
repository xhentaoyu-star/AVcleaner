from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_empty_state_helper_is_used_for_table_and_detail_panel() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "function emptyStateNode" in text
    assert "function emptyRow" in text
    assert "未分析" in text
    assert "未生成预览" in text
    assert "没有符合当前筛选的项目" in text
    assert "未选择项目" in text


def test_empty_state_has_icon_and_compact_style() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert ".empty-state" in css
    assert ".empty-state .icon" in css
