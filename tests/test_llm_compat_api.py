from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_file

import avcleaner.llm_review as review
from avcleaner.llm import LLMResponseError
from avcleaner.models import LLMBatchResponse, LLMSuggestion
from avcleaner.repository import get_plan, list_llm_suggestions


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def configure_llm(client, headers: dict[str, str], *, compatibility_mode: str = "claude_gateway_compat") -> dict:
    settings = client.get("/api/settings", headers=headers).json()
    settings["llm"]["provider"] = "openai_compatible"
    settings["llm"]["base_url"] = "https://gateway.example/v1"
    settings["llm"]["model"] = "mock-claude-gateway"
    settings["llm"]["compatibility_mode"] = compatibility_mode
    response = client.put("/api/settings", headers=headers, json=settings)
    assert response.status_code == 200
    return response.json()


def test_llm_test_endpoint_reports_stage_specific_parse_error(client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    configure_llm(client, auth_headers)

    async def fake_suggest(_request, _settings):
        raise LLMResponseError(
            "llm_missing_required_field",
            stage="schema",
            field_path="suggestions.0.language_suffix",
            sanitized_message="LLM response is missing a required field.",
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post("/api/llm/test", headers=auth_headers, json={})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "llm_missing_required_field"
    assert body["stage"] == "schema"
    assert body["field_path"] == "suggestions.0.language_suffix"
    assert body["compatibility_mode"] == "claude_gateway_compat"
    assert "Authorization" not in response.text


def test_plan_suggest_maps_parser_error_to_stable_api_error(
    tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)

    async def fake_suggest(_request, _settings):
        raise LLMResponseError("llm_no_json_object", stage="parse", sanitized_message="LLM response did not contain JSON.")

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [plan["items"][0]["id"]], "include_neighbors": True, "use_cache": False},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "llm_no_json_object"
    assert "movie_without_code" not in response.text


def test_plan_suggest_stores_invalid_path_like_suggestion_but_does_not_cache_or_mutate_plan(
    tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    original_hash = plan["plan_hash"]

    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[
                LLMSuggestion(
                    item_id=item["id"],
                    suggested_name="C:\\Temp\\ABP-123.mp4",
                    media_code="ABP-123",
                    part_suffix="",
                    variant="",
                    language_suffix="",
                    removed_tokens=[],
                    confidence=0.9,
                    reason="bad path",
                    warnings=[],
                )
            ]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True, "use_cache": True},
    )

    assert response.status_code == 200
    suggestion = response.json()["suggestions"][0]
    assert suggestion["status"] == "invalid"
    assert "llm_path_like_suggestion" in suggestion["warnings"]
    assert get_plan(plan["plan_id"]).plan_hash == original_hash
    assert list_llm_suggestions(plan["plan_id"])[0].status == "invalid"


def test_cache_key_changes_with_compatibility_mode(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_llm(client, auth_headers, compatibility_mode="openai_strict_json_schema")
    plan = create_plan(client, auth_headers, tmp_path)
    record = get_plan(plan["plan_id"])
    item = record.items[0]
    preview = review._payload_preview(item, record.items, True, False)
    strict_key = review._cache_key("openai_compatible", "mock-claude-gateway", item, preview)

    configure_llm(client, auth_headers, compatibility_mode="claude_gateway_compat")
    compat_key = review._cache_key("openai_compatible", "mock-claude-gateway", item, preview)

    assert strict_key != compat_key
