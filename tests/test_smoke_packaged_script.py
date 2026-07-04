from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_smoke_packaged_temp_execution_is_opt_in_and_temp_only() -> None:
    text = (ROOT / "scripts" / "smoke_packaged.ps1").read_text(encoding="utf-8")

    assert "[switch]$RunTempExecution" in text
    assert "avcleaner-smoke-" in text
    assert "Set-Content" in text
    assert "[ads.example] ABP123.mp4" in text
    assert "junk.url" in text
    assert "ABP-123.zh.srt" in text
    assert "if ($RunTempExecution)" in text
    assert "/api/plans/$($Plan.plan_id)/execution-summary" in text
    assert "/api/plans/$($Plan.plan_id)/execute" in text
    assert "/api/runs/$($execution.run_id)/rollback" in text


def test_smoke_packaged_preserves_debug_temp_directories_on_failure() -> None:
    text = (ROOT / "scripts" / "smoke_packaged.ps1").read_text(encoding="utf-8")

    assert "$completed = $false" in text
    assert "$completed = $true" in text
    assert "Preserving packaged smoke temp app" in text
    assert "Preserving packaged smoke scan root" in text
