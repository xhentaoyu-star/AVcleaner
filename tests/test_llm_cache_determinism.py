from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_file

import avcleaner.llm_review as review
from avcleaner.models import LLMBatchResponse, LLMSuggestion
from avcleaner.repository import get_plan


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def configure_mock_llm(client, headers: dict[str, str], provider: str = "ollama", model: str = "mock-model") -> None:
    settings = client.get("/api/settings", headers=headers).json()
    settings["llm"]["provider"] = provider
    settings["llm"]["model"] = model
    response = client.put("/api/settings", headers=headers, json=settings)
    assert response.status_code == 200


def cache_parts(plan_id: str, item_index: int = 0, include_neighbors: bool = True, provider: str = "ollama", model: str = "mock-model") -> tuple[str, str]:
    plan = get_plan(plan_id)
    item = plan.items[item_index]
    preview = review._payload_preview(item, plan.items, include_neighbors, False)
    return review._cache_key(provider, model, item, preview)


def test_cache_key_is_deterministic_for_same_inputs(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    make_file(tmp_path, "nearby_ABP-124.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    assert cache_parts(plan["plan_id"]) == cache_parts(plan["plan_id"])


def test_cache_key_changes_with_provider_model_schema_prompt_ruleset_neighbors_and_sidecar(
    tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    make_file(tmp_path, "nearby_ABP-124.mp4")
    make_file(tmp_path, "ABP-123.zh.srt")
    plan = create_plan(client, auth_headers, tmp_path)
    base = cache_parts(plan["plan_id"])

    assert cache_parts(plan["plan_id"], provider="openai_compatible") != base
    assert cache_parts(plan["plan_id"], model="other-model") != base
    assert cache_parts(plan["plan_id"], include_neighbors=False) != base
    assert cache_parts(plan["plan_id"], item_index=1) != base

    monkeypatch.setattr(review, "SCHEMA_VERSION", review.SCHEMA_VERSION + 1)
    assert cache_parts(plan["plan_id"]) != base
    monkeypatch.setattr(review, "SCHEMA_VERSION", 1)
    monkeypatch.setattr(review, "PROMPT_VERSION", "different-prompt")
    assert cache_parts(plan["plan_id"]) != base

    stored = get_plan(plan["plan_id"])
    item = stored.items[0].model_copy(update={"ruleset_hash": "different"})
    preview = review._payload_preview(item, stored.items, True, False)
    assert review._cache_key("ollama", "mock-model", item, preview) != base


def test_cache_hit_avoids_provider_call(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    calls = {"count": 0}

    async def fake_suggest(_request, _settings):
        calls["count"] += 1
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name="ABP-123.mp4", media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    payload = {"item_ids": [item["id"]], "include_neighbors": True, "use_cache": True}
    client.post(f"/api/plans/{plan['plan_id']}/llm/suggest", headers=auth_headers, json=payload)
    client.post(f"/api/plans/{plan['plan_id']}/llm/suggest", headers=auth_headers, json=payload)

    assert calls["count"] == 1
