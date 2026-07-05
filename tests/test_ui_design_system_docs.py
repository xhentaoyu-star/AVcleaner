from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "UI_DESIGN_SYSTEM.md"


def test_ui_design_system_doc_exists_and_mentions_core_contracts() -> None:
    text = DOC.read_text(encoding="utf-8")

    for marker in [
        "Tabler Icons regular outline",
        ".review-layout",
        "minmax()",
        "clamp()",
        ".detail-panel",
        "Settings",
        "Secrets",
    ]:
        assert marker in text
