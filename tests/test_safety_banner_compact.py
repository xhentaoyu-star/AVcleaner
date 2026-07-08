from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_first_use_helper_is_compact_and_expandable() -> None:
    html = HTML.read_text(encoding="utf-8")

    assert 'id="firstRunHelper" class="notice safety-compact"' in html
    assert 'id="firstRunDetails"' in html
    assert 'id="firstRunLearnBtn"' in html
    assert 'id="firstRunDismissBtn"' in html
    assert 'data-debug-only data-debug-field="safety-checklist"' in html


def test_safety_helper_uses_persisted_seen_flag() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    assert "renderFirstRunHelper()" in app_js
    assert "state.settings.first_run_seen = true" in app_js
    assert 'bindClick("#firstRunLearnBtn", toggleFirstRunDetails)' in app_js
