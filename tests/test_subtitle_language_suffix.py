from __future__ import annotations

import pytest

from avcleaner.rules import suggest_name_with_trace


@pytest.mark.parametrize(
    ("filename", "suggested_name", "media_code", "part_suffix", "variant", "language_suffix"),
    [
        ("ABP-123.zh.srt", "ABP-123.zh.srt", "ABP-123", "", "", "zh"),
        ("[ad] ABP123.chs.ass", "ABP-123.chs.ass", "ABP-123", "", "", "chs"),
        ("ABP-123.cht.ssa", "ABP-123.cht.ssa", "ABP-123", "", "", "cht"),
        ("ABP-123.en.srt", "ABP-123.en.srt", "ABP-123", "", "", "en"),
        ("ABP-123.ja.srt", "ABP-123.ja.srt", "ABP-123", "", "", "ja"),
        ("ABP-123.zh-CN.srt", "ABP-123.zh-CN.srt", "ABP-123", "", "", "zh-CN"),
        ("ABP-123.zh_TW.ass", "ABP-123.zh_TW.ass", "ABP-123", "", "", "zh_TW"),
        ("FC2PPV-4856696.zh-Hans.srt", "FC2PPV-4856696.zh-Hans.srt", "FC2PPV-4856696", "", "", "zh-Hans"),
        ("FC2-PPV-4856696_1.zh-CN.srt", "FC2PPV-4856696-1.zh-CN.srt", "FC2PPV-4856696", "-1", "", "zh-CN"),
        ("HEYZO-1234-C.en.srt", "HEYZO-1234-C.en.srt", "HEYZO-1234", "", "-C", "en"),
    ],
)
def test_subtitle_language_suffix_is_preserved(
    filename: str,
    suggested_name: str,
    media_code: str,
    part_suffix: str,
    variant: str,
    language_suffix: str,
) -> None:
    suggestion = suggest_name_with_trace(filename)

    assert suggestion.suggested_name == suggested_name
    assert suggestion.media_code == media_code
    assert suggestion.part_suffix == part_suffix
    assert suggestion.variant == variant
    assert suggestion.language_suffix == language_suffix
    assert any(step.rule_id == "detect_sidecar_language" for step in suggestion.trace)
    assert any(step.rule_id == "preserve_sidecar_language" for step in suggestion.trace)


def test_language_suffix_is_not_treated_as_variant() -> None:
    suggestion = suggest_name_with_trace("ABP-123.zh-CN.srt")

    assert suggestion.language_suffix == "zh-CN"
    assert suggestion.variant == ""
