from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js"


def test_analyze_clears_stale_preview_and_sets_busy_feedback() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    analyze = text[text.index("async function analyze") : text.index("async function scan")]

    assert "state.scan = null" in analyze
    assert "state.plan = null" in analyze
    assert "state.llmSuggestions = []" in analyze
    assert 'setBusy("analyzing", true)' in analyze
    assert 'setBusy("requestingAi", true)' in analyze
    assert 'setLoading("llm")' in analyze
    assert 'setLoading("analyze")' in analyze
    assert "AI 建议失败，已回退到规则预览" in analyze


def test_loading_labels_match_visible_analysis_stages() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    labels = text[text.index("const LOADING_LABELS") : text.index("function lookupExplanation")]

    for phrase in ["正在扫描", "正在生成预览", "正在请求 AI", "正在校验"]:
        assert phrase in labels
