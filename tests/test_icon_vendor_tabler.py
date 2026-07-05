from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "avcleaner" / "static" / "icon_registry.json"
VENDOR_ROOT = ROOT / "avcleaner" / "static" / "vendor" / "tabler-icons"


def test_tabler_outline_vendor_subset_exists() -> None:
    outline = VENDOR_ROOT / "outline"
    filled = VENDOR_ROOT / "filled"

    assert outline.is_dir()
    assert filled.is_dir()
    assert len(list(outline.glob("*.svg"))) < 80


def test_tabler_vendor_sources_match_registry() -> None:
    entries = json.loads(REGISTRY.read_text(encoding="utf-8"))
    referenced = {entry["source"] for entry in entries}
    vendored = {
        str(path.relative_to(VENDOR_ROOT)).replace("\\", "/")
        for path in VENDOR_ROOT.glob("*/*.svg")
    }

    assert referenced <= vendored
    assert vendored - referenced == set()


def test_outline_icons_keep_tabler_regular_shape() -> None:
    entries = json.loads(REGISTRY.read_text(encoding="utf-8"))

    for entry in entries:
        if entry["style"] != "outline":
            continue
        text = (VENDOR_ROOT / entry["source"]).read_text(encoding="utf-8")
        assert 'viewBox="0 0 24 24"' in text
        assert 'stroke-width="2"' in text
        assert 'stroke-linecap="round"' in text
        assert 'stroke-linejoin="round"' in text
