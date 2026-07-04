from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_file

from avcleaner.models import LLMBatchResponse, LLMSuggestion


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def configure_mock_llm(client, headers: dict[str, str]) -> None:
    settings = client.get("/api/settings", headers=headers).json()
    settings["llm"]["provider"] = "ollama"
    settings["llm"]["model"] = "mock-model"
    response = client.put("/api/settings", headers=headers, json=settings)
    assert response.status_code == 200


def create_suggestion(client, headers, plan: dict, item_id: str, monkeypatch: pytest.MonkeyPatch) -> dict:
    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item_id, suggested_name="ABP-123.mp4", media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=headers,
        json={"item_ids": [item_id], "include_neighbors": True, "use_cache": False},
    )
    assert response.status_code == 200
    return response.json()["suggestions"][0]


def test_manual_target_edit_marks_pending_suggestions_stale(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item_id = plan["items"][0]["id"]
    suggestion = create_suggestion(client, auth_headers, plan, item_id, monkeypatch)

    patch = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{item_id}",
        headers=auth_headers,
        json={"target_name": "MAN-001.mp4"},
    )
    listed = client.get(f"/api/plans/{plan['plan_id']}/llm/suggestions", headers=auth_headers).json()["suggestions"]

    assert patch.status_code == 200
    assert next(row for row in listed if row["suggestion_id"] == suggestion["suggestion_id"])["status"] == "stale"


def test_accepting_stale_suggestion_is_rejected(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item_id = plan["items"][0]["id"]
    suggestion = create_suggestion(client, auth_headers, plan, item_id, monkeypatch)
    patch = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{item_id}",
        headers=auth_headers,
        json={"target_name": "MAN-001.mp4"},
    ).json()

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": patch["plan_hash"]},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "suggestion_stale"


def test_rejecting_stale_suggestion_is_allowed(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item_id = plan["items"][0]["id"]
    suggestion = create_suggestion(client, auth_headers, plan, item_id, monkeypatch)
    client.patch(
        f"/api/plans/{plan['plan_id']}/items/{item_id}",
        headers=auth_headers,
        json={"target_name": "MAN-001.mp4"},
    )

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/reject",
        headers=auth_headers,
        json={"reason_code": "user_rejected"},
    )

    assert response.status_code == 200
    assert response.json()["suggestion"]["status"] == "rejected"
