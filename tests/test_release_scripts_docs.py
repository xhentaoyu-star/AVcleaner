from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_smoke_packaged_checks_supported_endpoints_without_execute() -> None:
    text = (ROOT / "scripts" / "smoke_packaged.ps1").read_text(encoding="utf-8")

    assert "[switch]$RunTempExecution" in text
    assert "/api/capabilities" in text
    assert "/api/health" in text
    assert "/api/execute" in text
    assert "/api/llm/suggest" in text
    assert "/api/scan" in text
    assert "/api/plans" in text
    assert "/validate" in text
    assert "/execution-summary" in text
    assert "/rollback" in text
    assert "if ($RunTempExecution)" in text
    assert "--no-window" in text
    assert "--portable" in text


def test_check_script_packaging_mode_is_optional() -> None:
    text = (ROOT / "scripts" / "check.ps1").read_text(encoding="utf-8")

    assert "[switch]$WithPackaging" in text
    assert "check_artifact.ps1" in text
    assert "smoke_packaged.ps1" in text
    assert "-RunTempExecution" in text
    assert "Packaging checks skipped" in text


def test_release_checklist_documents_required_gates() -> None:
    text = (ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")

    assert "scripts\\check.ps1" in text
    assert "build_portable.ps1" in text
    assert "check_artifact.ps1" in text
    assert "smoke_packaged.ps1" in text
    assert "legacy_execute_disabled" in text
    assert "legacy_llm_suggest_disabled" in text
    assert "Windows 10/11 x64" in text
    assert "-RunTempExecution" in text
    assert "create_release_zip.ps1" in text
    assert "path with spaces" in text


def test_packaging_readme_documents_portable_mode_and_no_secrets() -> None:
    text = (ROOT / "packaging" / "README.md").read_text(encoding="utf-8")

    assert "PyInstaller" in text
    assert "create_release_zip.ps1" in text
    assert "-RunTempExecution" in text
    assert "portable.flag" in text
    assert "data" in text
    assert "logs" in text
    assert "quarantine" in text
    assert "API keys" in text
