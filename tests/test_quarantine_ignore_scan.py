from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.models import ScanRequest
from avcleaner.quarantine import choose_quarantine_root
from avcleaner.scanner import QUARANTINE_DIR_NAME, scan_files


def test_scanner_ignores_avcleaner_quarantine_directory(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path / QUARANTINE_DIR_NAME / "run_1", "ad.url", b"junk")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))

    assert [item.name for item in scan.files] == ["hhd800.com@ABP-123.mp4"]


def test_quarantine_root_prefers_scan_root(tmp_path: Path) -> None:
    source = make_file(tmp_path / "sub", "ad.url", b"junk")

    root = choose_quarantine_root(tmp_path, source, "run_1")

    assert root == tmp_path / QUARANTINE_DIR_NAME / "run_1"
    assert root.exists()
