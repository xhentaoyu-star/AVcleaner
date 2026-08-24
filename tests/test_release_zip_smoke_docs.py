from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_final_release_zip_smoke_helper_exists_and_preserves_failure_artifacts() -> None:
    text = (ROOT / "scripts" / "smoke_release_zip.ps1").read_text(encoding="utf-8")

    assert "Expand-Archive" in text
    assert "smoke_packaged.ps1" in text
    assert "-RunTempExecution" in text
    assert "Remove-Item" in text
    assert "Preserving temp directory" in text


def test_release_checklist_documents_final_zip_smoke_commands() -> None:
    text = (ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

    assert "smoke_release_zip.ps1" in text
    assert "AVcleaner-v0.8.4-portable-win-x64.zip" in text
    assert "Get-FileHash" in text
    assert "SHA256" in text
