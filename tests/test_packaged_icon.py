from __future__ import annotations

import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "pyinstaller" / "avcleaner.spec"
ICON = ROOT / "packaging" / "pyinstaller" / "avcleaner.ico"


def test_portable_exe_uses_project_icon() -> None:
    spec = SPEC.read_text(encoding="utf-8")
    assert 'ICON = ROOT / "packaging" / "pyinstaller" / "avcleaner.ico"' in spec
    assert "icon=str(ICON)" in spec


def test_project_icon_contains_windows_sizes() -> None:
    data = ICON.read_bytes()
    reserved, icon_type, count = struct.unpack_from("<HHH", data, 0)
    assert reserved == 0
    assert icon_type == 1
    assert count >= 5

    sizes = []
    for index in range(count):
        offset = 6 + index * 16
        width = data[offset] or 256
        height = data[offset + 1] or 256
        sizes.append((width, height))

    assert (16, 16) in sizes
    assert (32, 32) in sizes
    assert (48, 48) in sizes
    assert (256, 256) in sizes
