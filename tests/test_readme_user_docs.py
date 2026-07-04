from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_mentions_v061_rc_workflow_and_safety_boundaries() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Current version: `0.6.1`" in text
    assert "Release candidate GUI workflow" in text
    assert "隔离不是永久删除" in text
    assert "阻止" in text
    assert "警告" in text
    assert "需复核" in text
    assert "legacy_execute_disabled" in text
    assert "legacy_llm_suggest_disabled" in text
    assert "OpenAver" in text
    assert "Compatibility mode does not bypass validation" in text
    assert "SHA256" in text


def test_quickstart_exists_for_nontechnical_beta_flow() -> None:
    text = (ROOT / "QUICKSTART.md").read_text(encoding="utf-8")

    for phrase in ["选择文件夹", "扫描", "生成预览", "复核", "执行选中", "回滚"]:
        assert phrase in text

    assert "隔离不是永久删除" in text
    assert "Strict OpenAI JSON Schema" in text
    assert "portable.flag" in text
