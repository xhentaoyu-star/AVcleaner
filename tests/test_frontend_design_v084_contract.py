from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_v084_workspace_has_responsive_and_accessible_hard_gates() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert 'data-workbench-version="0.8.4"' in html
    assert "button:focus-visible" in css
    assert "outline: 2px solid var(--accent)" in css
    assert "min-height: 40px" in css
    assert "button.danger" in css and "min-height: 44px" in css
    assert "@media (max-width: 820px)" in css
    assert "@media (max-width: 560px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (forced-colors: active)" in css


def test_sidebar_utility_buttons_and_active_navigation_are_operable() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    assert "function activateMainTab" in app_js
    assert 'item.setAttribute("aria-current", "page")' in app_js
    assert 'bindClick(\'[data-sidebar-tool="notice"]\', showLatestNotice)' in app_js
    assert 'bindClick(\'[data-sidebar-tool="help"]\', openHelpPanel)' in app_js


def test_settings_save_action_remains_available_in_every_settings_section() -> None:
    html = HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    settings = html[html.index('data-panel="settings"') : html.index('<div id="toast"')]
    assert settings.count('id="saveSettingsBtn"') == 1
    assert settings.index('data-settings-panel="diagnostics"') < settings.index('class="settings-actions"')
    assert 'id="settingsSaveStatus"' in settings
    assert "function markSettingsChanged" in app_js
    assert "有未保存的更改" in app_js
