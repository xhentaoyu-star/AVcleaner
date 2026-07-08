from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_execution_report_is_hidden_until_execution_exists() -> None:
    html = HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'id="executionReportPanel" class="execution-report" hidden data-empty-hidden' in html
    assert "panel.hidden = !report" in app_js
    assert 'id="executionSummaryResult" class="test-result compact-result" hidden data-debug-only' in html


def test_failed_items_block_is_collapsed_when_empty() -> None:
    html = HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'id="executionReportFailedBlock"' in html
    assert 'failedBlock.hidden = !report.failed_items.length' in app_js
