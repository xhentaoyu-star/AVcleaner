from __future__ import annotations

import json
from pathlib import Path

import pytest

from avcleaner.rules import suggest_name_with_trace

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "filenames"


def false_positive_rows() -> list[dict]:
    return json.loads((FIXTURE_ROOT / "false_positives.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("row", false_positive_rows(), ids=lambda row: row["input"])
def test_common_noise_tokens_are_not_media_codes(row: dict) -> None:
    suggestion = suggest_name_with_trace(row["input"])

    assert suggestion.media_code is None
    assert suggestion.suggested_name == row["expected_suggested_name"]
    assert suggestion.requires_review is True
    assert "media_code_not_detected" in suggestion.warnings
