from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_debug_mode_has_explicit_diagnostic_targets() -> None:
    html = HTML.read_text(encoding="utf-8")

    for marker in [
        'data-debug-only data-debug-field="capabilities"',
        'data-debug-only data-debug-field="runtime"',
        'data-debug-only data-debug-field="llm-raw"',
        'data-debug-only data-debug-field="diagnostics-raw"',
    ]:
        assert marker in html


def test_debug_details_are_rendered_only_in_debug_mode() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'if (isDebugMode()) body.append(detailSection("Debug' in app_js
    assert 'if (isDebugMode()) details.open = true' in app_js
    assert 'safeToastMessage' in app_js
