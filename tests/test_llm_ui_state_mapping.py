from __future__ import annotations

from pathlib import Path


def test_frontend_has_compact_llm_state_mapping_without_no_suggestion_spam() -> None:
    source = (Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js").read_text(encoding="utf-8")

    assert "const LLM_STATE_LABELS" in source
    assert "applied_to_preview" in source
    assert "rule_fallback" in source
    assert "无建议" not in source
