from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_main_ui_uses_combined_analyze_workflow() -> None:
    html = (ROOT / "avcleaner" / "templates" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "avcleaner" / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="analyzeBtn"' in html
    assert 'id="folderPickerBtn"' in html
    assert 'data-preview-mode="rule"' in html
    assert 'data-preview-mode="ai"' in html
    assert 'id="scanBtn"' not in html
    assert 'id="planBtn"' not in html
    assert "Step 4" not in html
    assert "/api/analyze" in app_js
