from __future__ import annotations

import os
from pathlib import Path

from avcleaner.models import ScanRequest
from avcleaner.scanner import scan_files


def test_recursive_scan_does_not_enter_excluded_directories(tmp_path: Path, monkeypatch) -> None:
    excluded = tmp_path / "skip-me"
    excluded.mkdir()
    (excluded / "hidden.mp4").write_bytes(b"video")
    (tmp_path / "visible.mp4").write_bytes(b"video")
    original_scandir = os.scandir

    def guarded_scandir(path):
        if Path(path).resolve() == excluded.resolve():
            raise AssertionError("excluded directory was traversed")
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded_scandir)

    result = scan_files(ScanRequest(root_path=str(tmp_path), exclude_dirs=["skip-me"]))

    assert [item.name for item in result.files] == ["visible.mp4"]
    assert str(excluded) in result.skipped_dirs
