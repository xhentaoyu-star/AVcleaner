from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / "THIRD_PARTY_NOTICES.md"


def test_third_party_notices_document_tabler_icons() -> None:
    text = NOTICE.read_text(encoding="utf-8")

    assert "Tabler Icons" in text
    assert "MIT License" in text
    assert "https://github.com/tabler/tabler-icons" in text
    assert "Copyright" in text
    assert "icon_registry.json" in text
