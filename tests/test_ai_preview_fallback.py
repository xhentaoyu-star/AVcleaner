from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.llm import LLMResponseError
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


def test_ai_preview_batches_uncached_items_by_configured_limit(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    for index in range(45):
        make_file(tmp_path, f"hhd800.com@ABP-{100 + index}.mp4")
    configure_llm(client, auth_headers)

    batch_sizes: list[int] = []

    async def fake_suggest(request, _settings):
        batch_sizes.append(len(request.items))
        return LLMBatchResponse(
            suggestions=[
                LLMSuggestion(
                    item_id=item.id,
                    suggested_name=item.rule_suggested_name,
                    media_code=item.media_code,
                    confidence=0.93,
                    reason="mock",
                )
                for item in request.items
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
    assert batch_sizes == [10, 10, 10, 10, 5]
    assert plan["llm_applied_count"] == 45
    assert plan["llm_invalid_count"] == 0


def test_ai_preview_splits_bad_batch_and_keeps_successful_items(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    for code in ["ABP-100", "ABP-101", "ABP-102", "ABP-103"]:
        make_file(tmp_path, f"hhd800.com@{code}.mp4")
    configure_llm(client, auth_headers)
    settings = client.get("/api/settings", headers=auth_headers).json()
    settings["llm"]["max_batch_size"] = 4
    response = client.put("/api/settings", headers=auth_headers, json=settings)
    assert response.status_code == 200

    batch_sizes: list[int] = []

    async def fake_suggest(request, _settings):
        batch_sizes.append(len(request.items))
        if any(item.media_code == "ABP-102" for item in request.items):
            raise LLMResponseError(
                "llm_multiple_json_objects",
                stage="parse",
                sanitized_message="mock multiple json objects",
            )
        return LLMBatchResponse(
            suggestions=[
                LLMSuggestion(
                    item_id=item.id,
                    suggested_name=f"{item.media_code.lower()}.mp4",
                    media_code=item.media_code,
                    confidence=0.93,
                    reason="mock",
                )
                for item in request.items
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
    items_by_code = {item["media_code"]: item for item in plan["items"]}
    assert batch_sizes == [4, 2, 2, 1, 1]
    assert plan["llm_applied_count"] == 3
    assert plan["llm_invalid_count"] == 1
    assert plan["llm_fallback_to_rule_count"] == 1
    assert "ai_preview_failed_fallback" not in plan["messages"]
    assert items_by_code["ABP-100"]["source"] == "llm"
    assert items_by_code["ABP-102"]["source"] == "rule"
    assert items_by_code["ABP-102"]["llm_error_code"] == "llm_multiple_json_objects"


def test_ai_preview_does_not_retry_a_timed_out_batch(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    for code in ["ABP-100", "ABP-101", "ABP-102", "ABP-103"]:
        make_file(tmp_path, f"hhd800.com@{code}.mp4")
    configure_llm(client, auth_headers)
    settings = client.get("/api/settings", headers=auth_headers).json()
    settings["llm"]["max_batch_size"] = 4
    assert client.put("/api/settings", headers=auth_headers, json=settings).status_code == 200

    batch_sizes: list[int] = []

    async def fake_suggest(request, _settings):
        batch_sizes.append(len(request.items))
        raise TimeoutError("mock timeout")

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)

    response = client.post(
        "/api/analyze",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "preview_mode": "ai"},
    )

    assert response.status_code == 200
    plan = response.json()["plan"]
    assert batch_sizes == [4]
    assert plan["llm_invalid_count"] == 4
    assert plan["llm_fallback_to_rule_count"] == 4
