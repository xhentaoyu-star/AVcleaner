from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
INDEX_HTML = ROOT / "avcleaner" / "templates" / "index.html"


def test_history_ui_has_filters_detail_and_export_controls() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    for marker in [
        "runFilterSelect",
        "runSummaryCards",
        "runDetailPanel",
        "runRollbackPreviewBtn",
        "runRollbackBtn",
        "runExportJsonBtn",
        "runExportCsvBtn",
    ]:
        assert marker in html
    for code in [
        "rollback-preview",
        "rollback_target_exists",
        "rollback_source_missing",
        "quarantine_file_missing",
        "rollback_file_changed",
        "unknown_run_item",
        "rollback_already_completed",
    ]:
        assert code in js


def test_history_ui_uses_stable_codes_with_friendly_mappings() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "friendlyCode" in text
    assert "CODE_EXPLANATIONS" in text
    assert "run_not_found" in text
    assert "rollback_not_available" in text
