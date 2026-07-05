from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.models import ScanRequest
from avcleaner.quarantine import choose_quarantine_root
from avcleaner.paths import quarantine_root
from avcleaner.scanner import QUARANTINE_DIR_NAME, scan_files


def test_scanner_ignores_avcleaner_quarantine_directory(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path / QUARANTINE_DIR_NAME / "run_1", "ad.url", b"junk")
    make_file(tmp_path / "quarantine" / "run_2", "movie.torrent", b"junk")

    scan = scan_files(ScanRequest(root_path=str(tmp_path)))

    assert [item.name for item in scan.files] == ["hhd800.com@ABP-123.mp4"]


def test_quarantine_root_defaults_outside_scan_root(tmp_path: Path) -> None:
    scan_root = tmp_path / "source"
    source = make_file(scan_root / "sub", "ad.url", b"junk")

    root = choose_quarantine_root(scan_root, source, "run_1")

    assert root == quarantine_root() / "run_1"
    assert not root.is_relative_to(scan_root)
    assert root.exists()


def test_quarantine_root_uses_custom_directory(tmp_path: Path) -> None:
    source = make_file(tmp_path / "sub", "ad.url", b"junk")
    custom = tmp_path / "custom-quarantine"

    root = choose_quarantine_root(tmp_path, source, "run_1", str(custom))

    assert root == custom / "run_1"
    assert root.exists()
