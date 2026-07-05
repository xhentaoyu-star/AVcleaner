from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_detail_drawer_shell_exists() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    for marker in [
        "detailDrawerPanel",
        "detail-panel detail-drawer",
        "detailDrawerTitle",
        "detailDrawerBody",
        "closeDetailDrawerBtn",
    ]:
        assert marker in html


def test_detail_drawer_contains_full_debug_context() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    for marker in [
        "function openDetailDrawer",
        "function closeDetailDrawer",
        "function renderDetailDrawer",
        "未选择项目",
        "emptyStateNode",
        "item_id",
        "source_rel_path",
        "target_name",
        "issueCodes(item)",
        "renderTraceList(item)",
        "renderSidecarDetails(item)",
        "llm_suggested_name",
        "JSON.stringify(item",
    ]:
        assert marker in text
