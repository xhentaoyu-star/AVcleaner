from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_explains_public_user_purpose_in_chinese() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    for phrase in [
        "BT 下载目录里的脏文件",
        "下载目录清理",
        "安全改名预览",
        "广告文件",
        "快捷方式",
        "残留说明",
        "可疑小文件",
        "隔离垃圾文件",
        "人工复核",
        "历史和回滚",
    ]:
        assert phrase in text

    assert "## 适合用来解决什么问题" in text
    assert "## 主要功能" in text
    assert "## 安全边界" in text
    assert "## 它不做什么" in text


def test_readme_is_not_a_version_changelog_or_local_machine_runbook() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## What v0.8.0 Adds" not in text
    assert "## What v0.7.5 Added" not in text
    assert "Local daily workflow" not in text
    assert "Current version:" not in text
    assert "cd L:\\1\\AVcleaner" not in text
    assert "L:\\1" not in text
    assert "普通用户建议直接下载 Releases 里的便携版" in text


def test_quickstart_is_for_public_users_not_this_machine() -> None:
    text = (ROOT / "QUICKSTART.md").read_text(encoding="utf-8")

    for phrase in [
        "这份文档是给普通使用者看的",
        "下载安装",
        "GitHub Releases",
        "AVcleaner.exe",
        "第一次使用",
        "选择一个 BT 下载完成后的文件夹",
        "执行摘要",
        "隔离不是永久删除",
        "如何恢复",
    ]:
        assert phrase in text

    assert "cd L:\\1\\AVcleaner" not in text
    assert ".venv" not in text
    assert "scripts\\check.ps1" not in text
    assert "AVcleaner-v0.8.0-portable-win-x64.zip" in text
