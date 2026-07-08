from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_settings_stays_modular_with_one_active_section() -> None:
    html = HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'class="panel settings-layout"' in html
    assert 'class="settings-subnav"' in html
    for tab in ["llm", "rules", "import-export", "diagnostics"]:
        assert f'data-settings-tab="{tab}"' in html
        assert f'data-settings-panel="{tab}"' in html
    assert "panel.hidden = panel.dataset.settingsPanel !== state.settingsTab" in app_js
    assert 'type="password"' in html
    assert "原始诊断 JSON" in html
