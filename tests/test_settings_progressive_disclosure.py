from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"


def test_settings_keeps_raw_json_collapsed_and_debug_marked() -> None:
    html = HTML.read_text(encoding="utf-8")

    for marker in [
        'id="llmRawJson" class="raw-json" data-debug-only data-debug-field="llm-raw"',
        'id="settingsExportRawJson" class="raw-json" data-debug-only data-debug-field="settings-export-raw"',
        'id="settingsImportRawJson" class="raw-json" data-debug-only data-debug-field="settings-import-raw"',
        'id="diagnosticsRawJson" class="raw-json" data-debug-only data-debug-field="diagnostics-raw"',
    ]:
        assert marker in html
    assert "<details open" not in html


def test_settings_has_user_relevant_sections_first() -> None:
    html = HTML.read_text(encoding="utf-8")

    for tab in ["llm", "rules", "import-export", "diagnostics"]:
        assert f'data-settings-tab="{tab}"' in html
        assert f'data-settings-panel="{tab}"' in html
    assert 'class="settings-summary"' in html
