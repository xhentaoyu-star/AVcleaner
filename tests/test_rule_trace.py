from __future__ import annotations

from pathlib import Path

from avcleaner.models import RuleSuggestion
from avcleaner.rules import VALID_RULE_IDS, suggest_name_with_trace


def test_suggest_name_with_trace_returns_structured_suggestion() -> None:
    suggestion = suggest_name_with_trace("[abc.com] FC2-PPV-4856696_1 1080p.mp4")

    assert isinstance(suggestion, RuleSuggestion)
    assert suggestion.suggested_name == "FC2PPV-4856696-1.mp4"
    assert suggestion.media_code == "FC2PPV-4856696"
    assert suggestion.part_suffix == "-1"
    assert suggestion.trace


def test_trace_steps_use_stable_rule_ids() -> None:
    suggestion = suggest_name_with_trace("hhd800.com@ABP-123-C.mp4")

    assert {step.rule_id for step in suggestion.trace}.issubset(VALID_RULE_IDS)


def test_final_trace_step_matches_suggested_name() -> None:
    suggestion = suggest_name_with_trace("HEYZO_1234_1080p.mp4")

    assert suggestion.trace[-1].rule_id == "render_template"
    assert suggestion.trace[-1].after == suggestion.suggested_name


def test_extension_is_preserved_by_default() -> None:
    suggestion = suggest_name_with_trace("FC2PPV1234567.MKV")

    assert Path(suggestion.suggested_name).suffix == ".mkv"


def test_no_confident_code_requires_review_with_warning() -> None:
    suggestion = suggest_name_with_trace("1080p x265 2024-01-01.mp4")

    assert suggestion.media_code is None
    assert suggestion.requires_review is True
    assert "media_code_not_detected" in suggestion.warnings
    assert suggestion.trace


def test_fc2_variants_normalize_to_single_format() -> None:
    names = [
        "FC2-PPV-1234567.mp4",
        "FC2PPV-1234567.mp4",
        "FC2PPV1234567.mp4",
    ]

    assert {suggest_name_with_trace(name).suggested_name for name in names} == {"FC2PPV-1234567.mp4"}
