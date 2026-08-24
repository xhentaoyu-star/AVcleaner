from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_top_level_operation_status_region_exists() -> None:
    html = HTML.read_text(encoding="utf-8")

    assert 'id="operationStatusChip"' in html
    assert 'aria-live="polite"' in html


def test_operation_status_maps_busy_and_plan_states() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")
    operation_start = app_js.index("function operationStatus()")
    operation_block = app_js[operation_start : app_js.index("function renderOperationStatus()", operation_start)]
    summary_start = app_js.index("function updateSummary()")
    summary_block = app_js[summary_start : app_js.index("function cell(", summary_start)]

    assert "function operationStatus()" in app_js
    for code in ["analyzing", "requesting_ai", "validating", "preview_ready", "blocked", "executable", "executed"]:
        assert code in app_js
    assert 'setText("#operationStatusChip", status.label)' in app_js
    assert "renderOperationStatus();" not in operation_block
    assert "updateSummaryCardVisibility(counts);" not in operation_block
    assert "renderOperationStatus();" in summary_block
    assert "updateSummaryCardVisibility(counts);" in summary_block
