from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_main_workflow_marks_technical_ids_debug_only() -> None:
    html = HTML.read_text(encoding="utf-8")

    for marker in [
        'data-debug-only data-debug-field="scan-id"',
        'data-debug-only data-debug-field="plan-id"',
        'data-debug-only data-debug-field="plan-hash"',
    ]:
        assert marker in html


def test_simple_mode_applies_hidden_attribute_to_debug_blocks() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'document.body.dataset.uiDetailMode = state.uiDetailMode' in app_js
    assert 'for (const node of document.querySelectorAll("[data-debug-only]"))' in app_js
    assert 'node.hidden = !isDebugMode()' in app_js
    assert 'for (const node of document.querySelectorAll("[data-simple-only]"))' in app_js
