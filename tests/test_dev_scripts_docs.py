from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_helper_scripts_use_project_venv() -> None:
    for name in ["test.ps1", "run.ps1", "corpus.ps1", "check.ps1"]:
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")

        assert ".venv\\Scripts\\python.exe" in text
    build_text = (ROOT / "packaging" / "build_portable.ps1").read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in build_text


def test_check_script_runs_required_commands() -> None:
    text = (ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")

    assert "-m pytest tests -q" in text
    assert "tools\\rule_corpus_report.py" in text
    assert "git diff --check" in text
    assert "node --check" in text
    assert "WithPackaging" in text


def test_readme_documents_venv_scripts() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert ".\\scripts\\check.ps1" in text
    assert ".venv\\Scripts\\python.exe" in text
    assert "bare python" in text
    assert "portable" in text.lower()
