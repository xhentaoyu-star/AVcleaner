from __future__ import annotations

import json
from pathlib import Path

import pytest

from avcleaner.rules import suggest_name_with_trace

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "filenames"
GOLDEN_FILES = [
    "fc2.json",
    "heyzo.json",
    "suke.json",
    "numeric_underscore.json",
    "ad_prefix_suffix.json",
    "bracket_ads.json",
    "part_suffixes.json",
    "segment_suffixes.json",
    "variants.json",
    "subtitle_language_suffixes.json",
]


def load_rows(name: str) -> list[dict]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("fixture_name", GOLDEN_FILES)
def test_golden_fixture_files_have_rows(fixture_name: str) -> None:
    assert load_rows(fixture_name)


@pytest.mark.parametrize(
    "row",
    [row for fixture in GOLDEN_FILES for row in load_rows(fixture)],
    ids=lambda row: row["input"],
)
def test_golden_filename_suggestions(row: dict) -> None:
    suggestion = suggest_name_with_trace(row["input"])

    assert suggestion.suggested_name == row["expected_suggested_name"]
    assert suggestion.media_code == row["expected_code"]
    assert suggestion.part_suffix == row["expected_part_suffix"]
    assert suggestion.variant == row["expected_variant"]
    if "expected_language_suffix" in row:
        assert suggestion.language_suffix == row["expected_language_suffix"]
    assert suggestion.requires_review is row["should_review"]
    for code in row["expected_warning_codes"]:
        assert code in suggestion.warnings
    assert suggestion.trace


def test_fixture_minimum_counts() -> None:
    assert len(load_rows("fc2.json")) >= 15
    assert len(load_rows("heyzo.json")) >= 8
    assert len(load_rows("suke.json")) >= 8
    assert len(load_rows("numeric_underscore.json")) >= 8
    assert len(load_rows("ad_prefix_suffix.json")) + len(load_rows("bracket_ads.json")) >= 15
    assert len(load_rows("part_suffixes.json")) + len(load_rows("variants.json")) >= 15
    assert len(load_rows("false_positives.json")) >= 20
    assert len(load_rows("junk_files.json")) + len(load_rows("associated_files.json")) >= 10
