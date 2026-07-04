from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pyinstaller_non_blocking_warnings_are_documented() -> None:
    text = (ROOT / "packaging" / "README.md").read_text(encoding="utf-8")

    assert "pycparser.lextab" in text
    assert "pycparser.yacctab" in text
    assert "tzdata" in text
    assert "non-blocking" in text.lower()
