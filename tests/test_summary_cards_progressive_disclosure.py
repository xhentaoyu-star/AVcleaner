from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_simple_summary_cards_identify_essential_and_conditional_cards() -> None:
    html = HTML.read_text(encoding="utf-8")

    for metric in ["files", "rename", "quarantine", "selected", "blocking"]:
        assert f'data-summary-card="{metric}" data-card-priority="essential"' in html
    for metric in ["warning", "requires-review", "manual", "sidecar"]:
        assert f'data-summary-card="{metric}" data-card-priority="conditional"' in html


def test_summary_card_visibility_is_updated_from_counts() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    assert "updateSummaryCardVisibility" in app_js
    assert 'card.dataset.cardPriority === "conditional"' in app_js
    assert "state.filter === card.dataset.filter" in app_js
