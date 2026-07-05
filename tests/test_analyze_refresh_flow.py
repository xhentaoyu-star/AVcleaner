from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js"


def test_analyze_clears_stale_preview_while_request_is_running() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    analyze_start = text.index("async function analyze")
    analyze_body = text[analyze_start : text.index("async function scan", analyze_start)]

    assert "const previousScan = state.scan" in analyze_body
    assert "const previousPlan = state.plan" in analyze_body
    assert "state.scan = null" in analyze_body
    assert "state.plan = null" in analyze_body
    assert "renderPlan();" in analyze_body
    assert 'api("/api/analyze"' in analyze_body
    assert "state.scan = previousScan" in analyze_body
    assert "state.plan = previousPlan" in analyze_body


def test_analyze_renders_preview_after_loading_state_clears() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    analyze_start = text.index("async function analyze")
    analyze_body = text[analyze_start : text.index("async function scan", analyze_start)]
    finally_start = analyze_body.index("finally")
    finally_body = analyze_body[finally_start:]

    assert 'setBusy("analyzing", false)' in finally_body
    assert 'setLoading("");' in finally_body
    assert 'setLoading("");\n    renderPlan();' in finally_body


def test_ai_analyze_fallback_is_visible() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "ai_preview_failed_fallback" in text
    assert "AI 建议失败，已回退到规则预览。" in text
