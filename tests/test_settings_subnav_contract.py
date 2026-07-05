from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_settings_page_uses_subnav_sections() -> None:
    html = HTML.read_text(encoding="utf-8")

    assert 'class="panel settings-layout"' in html
    assert 'class="settings-subnav"' in html
    for tab in ["llm", "rules", "import-export", "diagnostics"]:
        assert f'data-settings-tab="{tab}"' in html
        assert f'data-settings-panel="{tab}"' in html


def test_settings_subnav_shows_one_section_at_a_time() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert "function setupSettingsTabs" in app_js
    assert "panel.hidden = panel.dataset.settingsPanel !== state.settingsTab" in app_js
    assert ".settings-section[hidden]" in css


def test_settings_page_exposes_quarantine_directory_setting() -> None:
    html = HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'id="quarantineDir"' in html
    assert "不会把隔离文件夹放进源文件夹" in html
    assert "state.settings.quarantine_dir" in app_js
