from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_create_release_zip_script_has_safe_defaults() -> None:
    text = (ROOT / "packaging" / "create_release_zip.ps1").read_text(encoding="utf-8")

    assert 'AVcleaner-v$Version-portable-win-x64.zip' in text
    assert "Compress-Archive" in text
    assert "Get-FileHash" in text
    assert "artifact-manifest.json" in text
    assert "AVcleaner.exe" in text
    assert ".venv" in text
    assert "__pycache__" in text
    assert ".pytest_cache" in text
    assert "*.db" in text
    assert "quarantine" in text
    assert "logs" in text


def test_create_release_zip_script_can_build_optionally() -> None:
    text = (ROOT / "packaging" / "create_release_zip.ps1").read_text(encoding="utf-8")

    assert "[switch]$Build" in text
    assert "build_portable.ps1" in text
    assert "if ($Build)" in text
