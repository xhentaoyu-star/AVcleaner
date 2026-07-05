from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "avcleaner" / "static" / "icon_registry.json"
VENDOR_ROOT = ROOT / "avcleaner" / "static" / "vendor" / "tabler-icons"


def test_icon_registry_uses_tabler_outline_by_default() -> None:
    entries = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert entries
    assert all(entry["style"] in {"outline", "filled"} for entry in entries)
    assert any(entry["style"] == "outline" for entry in entries)
    for entry in entries:
        assert entry["source"].startswith(f'{entry["style"]}/')


def test_icon_registry_entries_have_vendor_sources() -> None:
    entries = json.loads(REGISTRY.read_text(encoding="utf-8"))
    symbols = [entry["symbol"] for entry in entries]

    assert len(symbols) == len(set(symbols))
    for entry in entries:
        source = VENDOR_ROOT / entry["source"]
        assert source.exists(), entry
        assert entry["tabler_name"] in source.name
        source_text = source.read_text(encoding="utf-8")
        assert source_text.lstrip().startswith("<!--") or "<svg" in source_text
