from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_active_ui_uses_local_icon_sprite_and_vendored_tabler_subset() -> None:
    html = (ROOT / "avcleaner" / "templates" / "index.html").read_text(encoding="utf-8")
    registry = json.loads((ROOT / "avcleaner" / "static" / "icon_registry.json").read_text(encoding="utf-8"))

    assert "/static/icons.svg#icon-" in html
    assert all(entry["source"].startswith("outline/") for entry in registry)
    assert (ROOT / "avcleaner" / "static" / "vendor" / "tabler-icons" / "outline").is_dir()
    for forbidden in ["cdn.jsdelivr", "unpkg.com", "cdnjs.cloudflare.com", "tabler-icons.io", "@tabler/icons"]:
        assert forbidden not in html
