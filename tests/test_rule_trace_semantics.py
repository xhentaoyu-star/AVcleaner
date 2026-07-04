from __future__ import annotations

from avcleaner.rules import suggest_name_with_trace


def rule_ids(filename: str) -> list[str]:
    return [step.rule_id for step in suggest_name_with_trace(filename).trace]


def test_trace_shows_key_transformations_for_rule_rename() -> None:
    suggestion = suggest_name_with_trace("[abc.com] FC2-PPV-4856696_1 1080p.mp4")
    ids = [step.rule_id for step in suggestion.trace]

    assert len(ids) > 1
    assert "remove_ad_domain" in ids
    assert "remove_noise_token" in ids
    assert "detect_media_code" in ids
    assert "normalize_media_code" in ids
    assert "detect_part_suffix" in ids
    assert "preserve_extension" in ids
    assert ids[-1] == "render_template"


def test_trace_detects_media_code_when_media_code_is_present() -> None:
    suggestion = suggest_name_with_trace("HEYZO-1234.mp4")

    assert suggestion.media_code == "HEYZO-1234"
    assert "detect_media_code" in [step.rule_id for step in suggestion.trace]


def test_trace_renders_template_when_name_changes() -> None:
    suggestion = suggest_name_with_trace("FC2PPV1234567.mp4")

    assert suggestion.suggested_name != suggestion.original_name
    assert suggestion.trace[-1].rule_id == "render_template"
    assert suggestion.trace[-1].after == suggestion.suggested_name


def test_removed_tokens_record_removed_ad_and_noise_tokens() -> None:
    suggestion = suggest_name_with_trace("[abc.com] ABP-123 1080p WEB-DL.mp4")
    removed_by_rule = {step.rule_id: step.removed_tokens for step in suggestion.trace}

    assert "abc.com" in removed_by_rule["remove_ad_domain"]
    assert "1080p" in removed_by_rule["remove_noise_token"]
    assert "WEB-DL" in removed_by_rule["remove_noise_token"]


def test_trace_is_not_single_generic_step_for_renames() -> None:
    suggestion = suggest_name_with_trace("hhd800.com@ABP-123-C.mp4")

    assert suggestion.suggested_name == "ABP-123-C.mp4"
    assert len(suggestion.trace) >= 4
    assert {step.rule_id for step in suggestion.trace} != {"render_template"}
