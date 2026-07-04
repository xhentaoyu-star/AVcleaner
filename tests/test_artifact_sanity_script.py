from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_artifact.ps1"


def make_artifact(root: Path) -> Path:
    artifact = root / "AVcleaner"
    (artifact / "avcleaner" / "templates").mkdir(parents=True)
    (artifact / "avcleaner" / "static").mkdir(parents=True)
    (artifact / "AVcleaner.exe").write_bytes(b"fake exe")
    (artifact / "avcleaner" / "templates" / "index.html").write_text("<html></html>", encoding="utf-8")
    (artifact / "avcleaner" / "static" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (artifact / "README.md").write_text("AVcleaner package", encoding="utf-8")
    return artifact


def run_script(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_check_artifact_script_accepts_clean_artifact(tmp_path: Path) -> None:
    artifact = make_artifact(tmp_path)

    result = run_script(artifact)

    assert result.returncode == 0, result.stderr
    assert "Artifact sanity check passed" in result.stdout


def test_check_artifact_script_rejects_user_database(tmp_path: Path) -> None:
    artifact = make_artifact(tmp_path)
    (artifact / "avcleaner.db").write_text("not a package file", encoding="utf-8")

    result = run_script(artifact)

    assert result.returncode != 0
    assert "Forbidden runtime file" in (result.stderr + result.stdout)


def test_check_artifact_script_rejects_venv_directory(tmp_path: Path) -> None:
    artifact = make_artifact(tmp_path)
    (artifact / ".venv").mkdir()

    result = run_script(artifact)

    assert result.returncode != 0
    assert "Forbidden directory" in (result.stderr + result.stdout)
