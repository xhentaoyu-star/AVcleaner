from __future__ import annotations

import pytest
from pydantic import ValidationError

from avcleaner.models import RuleSettings
from avcleaner.rules import VALID_RULE_IDS, suggest_name_with_trace


def test_default_rule_settings_preserve_current_behavior() -> None:
    settings = RuleSettings()
    suggestion = suggest_name_with_trace("[ad] ABP123.chs.ass", settings)

    assert suggestion.suggested_name == "ABP-123.chs.ass"
    assert suggestion.media_code == "ABP-123"
    assert suggestion.language_suffix == "chs"
    assert settings.enabled_rules["remove_noise_token"] is True
    assert set(settings.enabled_rules) == VALID_RULE_IDS


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"output_template": "{bad}{ext}"}, "rule_settings_invalid_template"),
        ({"enabled_rules": {"unknown_rule": True}}, "rule_settings_unknown_rule"),
        ({"video_extensions": [".MP4", ".mp4"]}, "rule_settings_duplicate_extension"),
        ({"video_extensions": ["bad/mp4"]}, "rule_settings_invalid_extension"),
        ({"remove_ad_domains": ["bad/path.com"]}, "rule_settings_invalid_ad_domain"),
        ({"review_threshold": 2.0}, "rule_settings_invalid_review_threshold"),
        ({"max_filename_length": 10}, "rule_settings_invalid_max_filename_length"),
        ({"preserve_sidecar_language": False}, "rule_settings_sidecar_language_required"),
    ],
)
def test_invalid_rule_settings_have_stable_error_codes(payload: dict, expected_code: str) -> None:
    with pytest.raises(ValidationError) as exc:
        RuleSettings.model_validate(payload)

    assert any(error["ctx"]["error_code"] == expected_code for error in exc.value.errors())


def test_rule_settings_reject_duplicate_extensions_case_insensitively() -> None:
    with pytest.raises(ValidationError) as exc:
        RuleSettings.model_validate({"sidecar_extensions": {"subtitle": [".srt", ".SRT"]}})

    assert exc.value.errors()[0]["ctx"]["error_code"] == "rule_settings_duplicate_extension"
