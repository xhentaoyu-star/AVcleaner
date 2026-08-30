from __future__ import annotations

from avcleaner.models import RuleSettings
from avcleaner.rules import suggest_name_with_trace


def test_output_template_can_change_rule_suggestion() -> None:
    settings = RuleSettings(output_template="{code}{variant}{part}{language}{ext}")

    suggestion = suggest_name_with_trace("ABP-123_2-C.mp4", settings)

    assert suggestion.suggested_name == "ABP-123-C-2.mp4"


def test_disabled_bracket_ad_rule_keeps_bracket_text_in_trace() -> None:
    settings = RuleSettings(remove_bracket_ads=False, enabled_rules={"remove_bracket_ad": False})

    suggestion = suggest_name_with_trace("[promo] ABP-123.mp4", settings)

    assert suggestion.suggested_name == "ABP-123.mp4"
    assert not any(step.rule_id == "remove_bracket_ad" for step in suggestion.trace)


def test_custom_noise_tokens_affect_trace_and_suggestion() -> None:
    settings = RuleSettings(remove_noise_tokens=["customtag"])

    suggestion = suggest_name_with_trace("customtag ABP-123.mp4", settings)

    assert suggestion.suggested_name == "ABP-123.mp4"
    noise_steps = [step for step in suggestion.trace if step.rule_id == "remove_noise_token"]
    assert noise_steps
    assert "customtag" in noise_steps[0].removed_tokens


def test_media_code_style_can_preserve_existing_code_text() -> None:
    settings = RuleSettings(media_code_style="preserve_existing")

    suggestion = suggest_name_with_trace("ABP123.mp4", settings)

    assert suggestion.suggested_name == "ABP123.mp4"
    assert suggestion.media_code == "ABP123"


def test_preserve_existing_does_not_duplicate_compact_variant() -> None:
    settings = RuleSettings(media_code_style="preserve_existing")

    for source in ("SUPD-103C.mp4", "ABP123C.mp4"):
        suggestion = suggest_name_with_trace(source, settings)

        assert suggestion.suggested_name == source
        assert suggestion.variant == "-C"


def test_configured_suffix_removal_requires_manual_review() -> None:
    part = suggest_name_with_trace("ABP-123-00.mp4", RuleSettings(preserve_part_suffix=False))
    variant = suggest_name_with_trace("ABP-123-UNCENSORED.mp4", RuleSettings(preserve_variant=False))

    assert part.suggested_name == "ABP-123.mp4"
    assert "configured_part_suffix_removal" in part.warnings
    assert part.requires_review is True
    assert variant.suggested_name == "ABP-123.mp4"
    assert "configured_variant_removal" in variant.warnings
    assert variant.requires_review is True


def test_overlapping_noise_tokens_do_not_remove_adjacent_media_code_text() -> None:
    settings = RuleSettings(remove_noise_tokens=["WEB"])

    suggestion = suggest_name_with_trace("WEB-DL ABP-123.mp4", settings)

    assert suggestion.suggested_name == "ABP-123.mp4"
    assert suggestion.media_code == "ABP-123"
