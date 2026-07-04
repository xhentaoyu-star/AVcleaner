from __future__ import annotations

import pytest
from pydantic import ValidationError

from avcleaner.models import LLMSuggestionApplyRequest, LLMSuggestionPayloadPreview, LLMSuggestionRecord


def test_llm_suggestion_record_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LLMSuggestionRecord(
            suggestion_id="s1",
            plan_id="p1",
            item_id="i1",
            provider="ollama",
            model="mock",
            schema_version=1,
            suggested_name="ABP-123.mp4",
            media_code="ABP-123",
            confidence=0.9,
            status="valid",
            created_at="2026-07-04T00:00:00+00:00",
            payload_hash="p",
            response_hash="r",
            source_path="C:\\bad.mp4",
        )


def test_llm_apply_request_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LLMSuggestionApplyRequest(expected_plan_hash="h", source_path="C:\\bad.mp4")  # type: ignore[call-arg]


def test_llm_payload_preview_shape_is_filename_only() -> None:
    preview = LLMSuggestionPayloadPreview(
        item_id="i1",
        filename="ABP-123.mp4",
        extension=".mp4",
        neighbor_filenames=["ABP-123.zh.srt"],
        rule_suggested_name="ABP-123.mp4",
        media_code="ABP-123",
        sidecar_type=None,
        language_suffix="",
        full_path_included=False,
    )

    assert preview.full_path_included is False
    assert "path" not in preview.model_dump()
