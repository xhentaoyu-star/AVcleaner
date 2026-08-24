from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "smoke_packaged.ps1"


def test_packaged_smoke_waits_for_process_and_retries_temp_cleanup() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "function Remove-DirectoryWithRetry" in text
    assert "Wait-Process -Id $process.Id -Timeout 10" in text
    assert "Remove-DirectoryWithRetry $tempAppRoot" in text
    assert "Start-Sleep -Milliseconds" in text
