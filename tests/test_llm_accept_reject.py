from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_file

from avcleaner.database import connect
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


def run_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]


def create_suggestion(client, headers: dict[str, str], plan: dict, item_id: str, monkeypatch: pytest.MonkeyPatch, name: str = "ABP-123.mp4") -> dict:
    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item_id, suggested_name=name, media_code="ABP-123", confidence=0.91, reason="mock")]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=headers,
        json={"item_ids": [item_id], "include_neighbors": True, "use_cache": False},
    )
    assert response.status_code == 200
    return response.json()["suggestions"][0]


def test_accept_requires_matching_plan_hash(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    suggestion = create_suggestion(client, auth_headers, plan, plan["items"][0]["id"], monkeypatch)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": "bad"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "plan_hash_mismatch"


def test_accept_updates_plan_item_but_does_not_execute_or_select(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    suggestion = create_suggestion(client, auth_headers, plan, item["id"], monkeypatch)
    before_runs = run_count()

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan_hash"] != plan["plan_hash"]
    assert body["item"]["target_name"] == "ABP-123.mp4"
    assert body["item"]["source"] == "llm"
    assert body["item"]["llm_accepted"] is True
    assert body["item"]["selected"] is False
    assert body["item"]["trace"][-1]["rule_id"] == "llm_accept"
    assert run_count() == before_runs


def test_reject_marks_suggestion_without_altering_plan(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    suggestion = create_suggestion(client, auth_headers, plan, item["id"], monkeypatch)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/reject",
        headers=auth_headers,
        json={"reason_code": "user_rejected"},
    )

    assert response.status_code == 200
    assert response.json()["suggestion"]["status"] == "rejected"
    stored = client.get(f"/api/plans/{plan['plan_id']}", headers=auth_headers).json()
    assert stored["items"][0]["target_name"] == item["target_name"]


def test_accept_revalidates_and_rejects_blocking_suggestion(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    suggestion = create_suggestion(client, auth_headers, plan, plan["items"][0]["id"], monkeypatch, name="ABP-123.mkv")

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "blocking_suggestion"
