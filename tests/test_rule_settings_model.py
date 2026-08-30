from __future__ import annotations

import pytest
from pydantic import ValidationError

from avcleaner.models import AppSettings, RuleSettings
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
        ({"output_template": "{code}{part}{variant}{ext}"}, "rule_settings_invalid_template"),
        ({"output_template": "{code}{code}{part}{variant}{language}{ext}"}, "rule_settings_invalid_template"),
        ({"output_template": "{code:.0}{part}{variant}{language}{ext}"}, "rule_settings_invalid_template"),
        ({"output_template": "{code!r}{part}{variant}{language}{ext}"}, "rule_settings_invalid_template"),
        ({"enabled_rules": {"unknown_rule": True}}, "rule_settings_unknown_rule"),
        ({"video_extensions": [".MP4", ".mp4"]}, "rule_settings_duplicate_extension"),
        ({"video_extensions": ["bad/mp4"]}, "rule_settings_invalid_extension"),
        ({"remove_ad_domains": ["bad/path.com"]}, "rule_settings_invalid_ad_domain"),
        ({"remove_ad_domains": ["00"]}, "rule_settings_invalid_ad_domain"),
        ({"remove_noise_tokens": ["00"]}, "rule_settings_invalid_remove_token"),
        ({"custom_remove_tokens": ["C"]}, "rule_settings_invalid_remove_token"),
        ({"junk_extensions": [".mp4"]}, "rule_settings_extension_role_conflict"),
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


@pytest.mark.parametrize(
    ("extension", "top_level_field", "rule_sidecar_group"),
    [
        (".mp4", "video_extensions", None),
        (".srt", "sidecar_extensions", "subtitle"),
    ],
)
def test_app_settings_reject_builtin_content_extension_as_junk_when_removed_from_role_lists(
    extension: str,
    top_level_field: str,
    rule_sidecar_group: str | None,
) -> None:
    payload = AppSettings().model_dump()
    payload[top_level_field].remove(extension)
    if rule_sidecar_group is None:
        payload["rules"]["video_extensions"].remove(extension)
    else:
        payload["rules"]["sidecar_extensions"][rule_sidecar_group].remove(extension)
    payload["rules"]["junk_extensions"].append(extension)

    with pytest.raises(ValidationError) as exc:
        AppSettings.model_validate(payload)

    assert exc.value.errors()[0]["ctx"]["error_code"] == "rule_settings_extension_role_conflict"


def test_rule_settings_migrates_legacy_fc2_style() -> None:
    settings = RuleSettings.model_validate({"fc2_style": "FC2PPV-1234567"})

    assert settings.fc2_style == "FC2-PPV-1234567"
