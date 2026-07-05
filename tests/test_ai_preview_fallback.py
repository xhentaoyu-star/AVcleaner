from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.models import LLMBatchResponse, LLMSuggestion

from test_ai_preview_mode import configure_llm


def test_ai_preview_invalid_suggestion_falls_back_to_rule_target(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    configure_llm(client, auth_headers)

    async def fake_suggest(request, _settings):
        return LLMBatchResponse(
            suggestions=[
                LLMSuggestion(
                    item_id=request.items[0].id,
                    suggested_name="ABP-123.mkv",
                    media_code="ABP-123",
                    confidence=0.93,
                    reason="mock invalid extension",
                )
            ]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)

    response = client.post(
        "/api/analyze",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "preview_mode": "ai"},
    )

    assert response.status_code == 200
    plan = response.json()["plan"]
    item = plan["items"][0]
    assert item["target_name"] == "ABP-123.mp4"
    assert item["source"] == "rule"
    assert item["llm_state"] == "safety_error"
    assert item["llm_error_code"] == "llm_extension_changed"
    assert plan["llm_invalid_count"] == 1
    assert plan["llm_fallback_to_rule_count"] == 1


def test_ai_preview_global_provider_failure_keeps_rule_preview(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    configure_llm(client, auth_headers)

    async def fake_suggest(_request, _settings):
        raise RuntimeError("network disabled in test")

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)

    response = client.post(
        "/api/analyze",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "preview_mode": "ai"},
    )

    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["items"][0]["target_name"] == "ABP-123.mp4"
    assert plan["items"][0]["llm_state"] == "provider_error"
    assert "ai_preview_failed_fallback" in plan["messages"]
