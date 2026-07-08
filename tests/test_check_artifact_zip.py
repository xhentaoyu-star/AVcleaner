from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

from test_artifact_manifest import make_dist, run_create_release_zip


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_artifact.ps1"


def run_check_artifact(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_check_artifact_accepts_release_zip_and_matching_checksum(tmp_path: Path) -> None:
    dist = make_dist(tmp_path / "dist")
    release_dir = tmp_path / "release"
    created = run_create_release_zip(dist, release_dir)
    assert created.returncode == 0, created.stderr + created.stdout

    result = run_check_artifact(release_dir / "AVcleaner-v0.7.5-portable-win-x64.zip")

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Artifact sanity check passed" in result.stdout


def test_release_zip_script_excludes_user_database_before_artifact_check(tmp_path: Path) -> None:
    dist = make_dist(tmp_path / "dist")
    (dist / "data").mkdir()
    (dist / "data" / "avcleaner.db").write_text("user db", encoding="utf-8")
    release_dir = tmp_path / "release"
    created = run_create_release_zip(dist, release_dir)
    assert created.returncode == 0, created.stderr + created.stdout

    result = run_check_artifact(release_dir / "AVcleaner-v0.7.5-portable-win-x64.zip")

    assert result.returncode == 0, result.stderr + result.stdout


def test_check_artifact_rejects_zip_that_contains_user_database(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("AVcleaner/AVcleaner.exe", b"fake exe")
        zf.writestr("AVcleaner/README.md", "AVcleaner")
        zf.writestr("AVcleaner/artifact-manifest.json", "{}")
        zf.writestr("AVcleaner/_internal/avcleaner/templates/index.html", "<html></html>")
        zf.writestr("AVcleaner/_internal/avcleaner/static/app.js", "console.log('ok')")
        zf.writestr("AVcleaner/data/avcleaner.db", "user db")

    result = run_check_artifact(zip_path)

    assert result.returncode != 0
    assert "Forbidden runtime file" in (result.stderr + result.stdout)
