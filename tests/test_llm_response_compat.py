from __future__ import annotations

import json

import pytest

from avcleaner.llm import (
    LLMProviderMode,
    LLMResponseError,
    LLM_SCHEMA,
    parse_llm_batch_response,
    provider_capabilities,
)


def suggestion_payload(**overrides):
    payload = {
        "item_id": "item-1",
        "suggested_name": "FC2-PPV-1234567-1.mp4",
        "media_code": "FC2-PPV-1234567",
        "part_suffix": "-1",
        "variant": "",
        "language_suffix": "",
        "removed_tokens": ["ad-site"],
        "confidence": 0.9,
        "reason": "Detected FC2 media code and part suffix.",
        "warnings": [],
    }
    payload.update(overrides)
    return payload


def batch_payload(**suggestion_overrides):
    return {"suggestions": [suggestion_payload(**suggestion_overrides)]}


def test_provider_capabilities_are_mode_specific() -> None:
    strict = provider_capabilities(LLMProviderMode.OPENAI_STRICT_JSON_SCHEMA)
    compat = provider_capabilities(LLMProviderMode.CLAUDE_GATEWAY_PROMPT_JSON)
    ollama = provider_capabilities(LLMProviderMode.OLLAMA_FORMAT_JSON)

    assert strict.supports_response_format_json_schema is True
    assert strict.supports_strict_json_schema is True
    assert strict.allow_json_extraction is False
    assert compat.supports_response_format_json_schema is False
    assert compat.allow_json_extraction is True
    assert compat.allow_single_suggestion_wrapping is True
    assert ollama.supports_ollama_format is True


def test_strict_schema_requires_language_suffix_and_blocks_extra_fields() -> None:
    item_schema = LLM_SCHEMA["properties"]["suggestions"]["items"]

    assert "language_suffix" in item_schema["required"]
    assert LLM_SCHEMA["additionalProperties"] is False
    assert item_schema["additionalProperties"] is False


def test_raw_json_batch_parses_in_strict_mode() -> None:
    parsed = parse_llm_batch_response(json.dumps(batch_payload()), LLMProviderMode.OPENAI_STRICT_JSON_SCHEMA)

    assert parsed.batch.suggestions[0].suggested_name == "FC2-PPV-1234567-1.mp4"
    assert parsed.json_extracted is False


@pytest.mark.parametrize(
    "raw",
    [
        "```json\n{payload}\n```",
        "```\n{payload}\n```",
        "Here is the JSON:\n{payload}\nDone.",
    ],
)
def test_compat_mode_extracts_fenced_or_surrounded_json(raw: str) -> None:
    content = raw.replace("{payload}", json.dumps(batch_payload()))

    parsed = parse_llm_batch_response(content, LLMProviderMode.CLAUDE_GATEWAY_PROMPT_JSON)

    assert parsed.batch.suggestions[0].item_id == "item-1"
    assert parsed.json_extracted is True


def test_compat_mode_wraps_single_suggestion_object() -> None:
    parsed = parse_llm_batch_response(json.dumps(suggestion_payload()), LLMProviderMode.CLAUDE_GATEWAY_PROMPT_JSON)

    assert len(parsed.batch.suggestions) == 1
    assert parsed.batch.suggestions[0].media_code == "FC2-PPV-1234567"


def test_compat_mode_wraps_suggestion_property() -> None:
    parsed = parse_llm_batch_response(json.dumps({"suggestion": suggestion_payload()}), LLMProviderMode.CLAUDE_GATEWAY_PROMPT_JSON)

    assert parsed.batch.suggestions[0].item_id == "item-1"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("not json", "llm_no_json_object"),
        ("{bad", "llm_invalid_json"),
        (json.dumps(batch_payload()) + "\n" + json.dumps(batch_payload()), "llm_multiple_json_objects"),
    ],
)
def test_parse_errors_have_stable_codes(raw: str, code: str) -> None:
    with pytest.raises(LLMResponseError) as exc_info:
        parse_llm_batch_response(raw, LLMProviderMode.CLAUDE_GATEWAY_PROMPT_JSON)

    assert exc_info.value.error_code == code
    assert exc_info.value.stage == "parse"


@pytest.mark.parametrize(
    ("payload", "code", "field_path"),
    [
        ({"suggestions": [{k: v for k, v in suggestion_payload().items() if k != "language_suffix"}]}, "llm_missing_required_field", "suggestions.0.language_suffix"),
        ({"suggestions": [suggestion_payload(extra="bad")]}, "llm_extra_field", "suggestions.0.extra"),
        ({"suggestions": [suggestion_payload(warnings="bad")]}, "llm_wrong_field_type", "suggestions.0.warnings"),
        ({"suggestions": [suggestion_payload(confidence=1.5)]}, "llm_confidence_out_of_range", "suggestions.0.confidence"),
        ({"item_id": "x"}, "llm_schema_invalid", "suggestions"),
    ],
)
def test_schema_errors_have_stable_codes(payload: dict, code: str, field_path: str) -> None:
    with pytest.raises(LLMResponseError) as exc_info:
        parse_llm_batch_response(json.dumps(payload), LLMProviderMode.CLAUDE_GATEWAY_PROMPT_JSON)

    assert exc_info.value.error_code == code
    assert exc_info.value.stage == "schema"
    assert exc_info.value.field_path == field_path


@pytest.mark.parametrize("suggested_name", ["../ABP-123.mp4", "C:\\Temp\\ABP-123.mp4", "file:///C:/ABP-123.mp4"])
def test_path_like_suggestions_are_rejected_after_parse(suggested_name: str) -> None:
    with pytest.raises(LLMResponseError) as exc_info:
        parse_llm_batch_response(
            json.dumps(batch_payload(suggested_name=suggested_name)),
            LLMProviderMode.CLAUDE_GATEWAY_PROMPT_JSON,
        )

    assert exc_info.value.error_code == "llm_path_like_suggestion"
    assert exc_info.value.stage == "safety"
    assert exc_info.value.field_path == "suggestions.0.suggested_name"
