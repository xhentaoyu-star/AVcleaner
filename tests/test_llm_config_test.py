from __future__ import annotations

import asyncio

import pytest

from avcleaner.llm import check_llm_settings
from avcleaner.models import LLMBatchResponse, LLMSuggestion, LLMSettings


def test_llm_test_reports_not_configured() -> None:
    response = asyncio.run(check_llm_settings(LLMSettings()))
    assert not response.ok
    assert response.error_code == "llm_not_configured"


def test_llm_test_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[
                LLMSuggestion(
                    item_id="test-item",
                    suggested_name="FC2-PPV-1234567-1.mp4",
                    media_code="FC2-PPV-1234567",
                    confidence=0.99,
                )
            ]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = asyncio.run(check_llm_settings(LLMSettings(provider="ollama", model="mock")))

    assert response.ok
    assert response.schema_valid
    assert "path" not in response.payload_preview


def test_llm_test_schema_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_suggest(_request, _settings):
        raise ValueError("bad schema")

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = asyncio.run(check_llm_settings(LLMSettings(provider="ollama", model="mock")))

    assert not response.ok
    assert response.error_code == "llm_schema_invalid"
