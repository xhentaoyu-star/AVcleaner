from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js"


def test_frontend_has_central_feedback_types_and_status_strip() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "const FEEDBACK_TYPES" in text
    for feedback_type in ["info", "success", "warning", "error", "loading"]:
        assert feedback_type in text
    assert "function sanitizeFeedbackMessage" in text
    assert "function showFeedback" in text
    assert "function setStatus" in text
    assert "lastOperationStatus" in text


def test_feedback_covers_main_async_workflows() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    for marker in [
        "分析中",
        "规则预览已生成",
        "AI 智能预览已生成",
        "AI 建议失败，已回退到规则预览。",
        "校验完成",
        "手动修改已保存",
        "导出完成",
        "执行完成",
        "回滚预览已生成",
        "设置已保存",
        "LLM 测试完成",
    ]:
        assert marker in text
