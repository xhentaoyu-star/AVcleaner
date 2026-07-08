from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_simple_mode_is_default_and_persisted_locally() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'uiDetailMode: loadUiDetailMode()' in app_js
    assert 'return value === "debug" ? "debug" : "simple"' in app_js
    assert 'localStorage.getItem(UI_DETAIL_MODE_KEY)' in app_js
    assert 'localStorage.setItem(UI_DETAIL_MODE_KEY, mode)' in app_js


def test_debug_mode_has_hidden_shortcut_without_settings_export() -> None:
    html = HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'id="debugModeToggle"' not in html
    assert 'id="settingsDebugModeToggle"' not in html
    assert 'data-ui-detail-toggle' not in html
    assert 'setupUiDetailModeControls()' in app_js
    assert 'event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "d"' in app_js
    assert "uiDetailMode" not in (ROOT / "avcleaner" / "models.py").read_text(encoding="utf-8")
