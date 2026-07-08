from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
INDEX_HTML = ROOT / "avcleaner" / "templates" / "index.html"


def test_execution_report_panel_contract() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    for marker in [
        "executionReportPanel",
        "executionReportRunId",
        "executionReportRenamed",
        "executionReportQuarantined",
        "executionReportFailedItems",
        "viewLastRunBtn",
        "previewLastRollbackBtn",
        "exportLastRunReportBtn",
    ]:
        assert marker in html
    assert "function executionReportFromResponse" in js
    assert "function executionReportFromRunDetail" in js
    assert "function waitForExecutionProgress" in js
    assert "renderExecutionReport" in js
    execute_start = js.index("async function executeSelected")
    progress_pos = js.index("waitForExecutionProgress", execute_start)
    report_pos = js.index("executionReportFromRunDetail", execute_start)
    refresh_pos = js.index("refreshRuns", execute_start)
    assert progress_pos < report_pos
    assert report_pos < refresh_pos


def test_execution_report_is_local_and_not_llm_flow() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    start = text.index("function executionReportFromResponse")
    end = text.index("async function showExecutionSummary", start)
    report_block = text[start:end]

    assert "/llm/" not in report_block
    assert "llmSuggest" not in report_block
