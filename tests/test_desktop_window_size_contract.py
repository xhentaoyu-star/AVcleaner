from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "avcleaner" / "desktop.py"


def test_desktop_wrapper_uses_v075_window_baseline() -> None:
    source = DESKTOP.read_text(encoding="utf-8")

    assert 'webview.create_window("AVcleaner"' in source
    assert "width=1440" in source
    assert "height=900" in source
    assert "min_size=(1280, 760)" in source
