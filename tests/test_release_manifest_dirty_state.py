from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_manifest_dirty_check_ignores_build_outputs_but_keeps_source_changes() -> None:
    text = (ROOT / "packaging" / "create_release_zip.ps1").read_text(encoding="utf-8")

    assert "Get-ReleaseGitStatus" in text
    assert "status --porcelain" in text
    assert "--untracked-files=normal" in text
    assert ":(exclude)dist" in text
    assert ":(exclude)build" in text
    assert ":(exclude)release" in text
    assert "git_dirty" in text


def test_packaging_docs_explain_clean_rebuild_dirty_state() -> None:
    text = (ROOT / "packaging" / "README.md").read_text(encoding="utf-8")

    assert "git_dirty=false" in text
    assert "dist/" in text
    assert "build/" in text
    assert "release/" in text
    assert "source changes" in text
