from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pyinstaller_spec_includes_templates_static_and_desktop_entrypoint() -> None:
    text = (ROOT / "packaging" / "pyinstaller" / "avcleaner.spec").read_text(encoding="utf-8")

    assert "avcleaner/static" in text
    assert "avcleaner/templates" in text
    assert "desktop.py" in text
    assert 'console=False' in text
    assert 'excludes=["pytest", "tests"]' in text


def test_build_portable_uses_project_venv_and_adds_portable_flag() -> None:
    text = (ROOT / "packaging" / "build_portable.ps1").read_text(encoding="utf-8")

    assert ".venv\\Scripts\\python.exe" in text
    assert "-m PyInstaller" in text
    assert "portable.flag" in text
    assert "README.md" in text
    assert "QUICKSTART.txt" in text


def test_pyinstaller_is_dev_dependency_not_runtime_import() -> None:
    dev = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").lower()
    runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()

    assert "pyinstaller" in dev
    assert "pyinstaller" not in runtime


def test_gitignore_allows_packaging_spec() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "*.spec" in text
    assert "!packaging/pyinstaller/*.spec" in text
    assert "release/" in text
