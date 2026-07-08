from __future__ import annotations

from avcleaner.rules import suggest_name_with_trace


def test_letter_segment_suffixes_are_preserved() -> None:
    examples = {
        "FSVSS-004-A.mp4": "FSVSS-004-A.mp4",
        "FSVSS-004-B.mp4": "FSVSS-004-B.mp4",
        "FSVSS004-b.mp4": "FSVSS-004-B.mp4",
        "FC2-PPV-1234567-A.mp4": "FC2-PPV-1234567-A.mp4",
        "HEYZO-1234-A.mp4": "HEYZO-1234-A.mp4",
    }

    for source, expected in examples.items():
        suggestion = suggest_name_with_trace(source)

        assert suggestion.suggested_name == expected
        assert suggestion.variant in {"-A", "-B"}
        assert suggestion.part_suffix == ""
        assert "detect_segment_suffix" in [step.rule_id for step in suggestion.trace]
        assert "preserve_segment_suffix" in [step.rule_id for step in suggestion.trace]


def test_numeric_segment_suffixes_still_use_part_suffix() -> None:
    suggestion = suggest_name_with_trace("ABP-123-2.mp4")

    assert suggestion.suggested_name == "ABP-123-2.mp4"
    assert suggestion.part_suffix == "-2"
    assert suggestion.variant == ""
    assert "detect_part_suffix" in [step.rule_id for step in suggestion.trace]
