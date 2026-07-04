from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "create_release_zip.ps1"


def make_dist(root: Path) -> Path:
    dist = root / "AVcleaner"
    (dist / "_internal" / "avcleaner" / "templates").mkdir(parents=True)
    (dist / "_internal" / "avcleaner" / "static").mkdir(parents=True)
    (dist / "AVcleaner.exe").write_bytes(b"fake exe")
    (dist / "_internal" / "avcleaner" / "templates" / "index.html").write_text("<html></html>", encoding="utf-8")
    (dist / "_internal" / "avcleaner" / "static" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    (dist / "README.md").write_text("AVcleaner", encoding="utf-8")
    (dist / "QUICKSTART.txt").write_text("Run AVcleaner.exe", encoding="utf-8")
    (dist / "portable.flag").write_text("", encoding="utf-8")
    return dist


def run_create_release_zip(dist: Path, release_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-DistPath",
            str(dist),
            "-ReleaseDir",
            str(release_dir),
            "-Version",
            "0.6.1",
            "-SmokeTested",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_release_zip_script_generates_zip_checksum_and_manifest(tmp_path: Path) -> None:
    dist = make_dist(tmp_path / "dist")
    release_dir = tmp_path / "release"

    result = run_create_release_zip(dist, release_dir)

    assert result.returncode == 0, result.stderr + result.stdout
    zip_path = release_dir / "AVcleaner-v0.6.1-portable-win-x64.zip"
    sha_path = release_dir / "AVcleaner-v0.6.1-portable-win-x64.zip.sha256"
    manifest_path = release_dir / "artifact-manifest.json"
    assert zip_path.exists()
    assert sha_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["app_name"] == "AVcleaner"
    assert manifest["version"] == "0.6.1"
    assert manifest["artifact_name"] == zip_path.name
    assert len(manifest["artifact_sha256"]) == 64
    assert manifest["smoke_tested"] is True
    assert all("L:\\\\" not in json.dumps(value) for value in manifest.values())

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "AVcleaner/AVcleaner.exe" in names
    assert "AVcleaner/artifact-manifest.json" in names
    assert not any("/.venv/" in name or "/tests/" in name for name in names)
