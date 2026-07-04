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


def create_suggestion(client, headers, plan: dict, item_id: str, monkeypatch: pytest.MonkeyPatch, suggested_name: str) -> dict:
    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item_id, suggested_name=suggested_name, media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=headers,
        json={"item_ids": [item_id], "include_neighbors": True, "use_cache": False},
    )
    assert response.status_code == 200
    return response.json()["suggestions"][0]


def test_accept_reject_requires_matching_hash_and_does_not_create_runs(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    suggestion = create_suggestion(client, auth_headers, plan, plan["items"][0]["id"], monkeypatch, "ABP-123.mp4")
    before_runs = run_count()

    mismatch = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": "bad"},
    )
    accepted = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": plan["plan_hash"]},
    )

    assert mismatch.status_code == 409
    assert mismatch.json()["error_code"] == "plan_hash_mismatch"
    assert accepted.status_code == 200
    assert accepted.json()["suggestion"]["status"] == "accepted"
    assert accepted.json()["plan_hash"] != plan["plan_hash"]
    assert accepted.json()["item"]["selected"] is False
    assert run_count() == before_runs


def test_accept_rejects_suggestion_from_another_plan(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    make_file(root_a, "movie_without_code.mp4")
    make_file(root_b, "other_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan_a = create_plan(client, auth_headers, root_a)
    plan_b = create_plan(client, auth_headers, root_b)
    suggestion = create_suggestion(client, auth_headers, plan_a, plan_a["items"][0]["id"], monkeypatch, "ABP-123.mp4")

    response = client.post(
        f"/api/plans/{plan_b['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": plan_b["plan_hash"]},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "suggestion_plan_mismatch"


def test_accept_revalidates_conflicts(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    review_item = next(item for item in plan["items"] if item["original_name"] == "movie_without_code.mp4")
    suggestion = create_suggestion(client, auth_headers, plan, review_item["id"], monkeypatch, "ABP-123.mp4")

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "blocking_suggestion"


def test_accept_marks_older_competing_suggestions_stale(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item_id = plan["items"][0]["id"]
    old = create_suggestion(client, auth_headers, plan, item_id, monkeypatch, "ABP-123.mp4")
    new = create_suggestion(client, auth_headers, plan, item_id, monkeypatch, "ABP-124.mp4")

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{new['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": plan["plan_hash"]},
    )
    listed = client.get(f"/api/plans/{plan['plan_id']}/llm/suggestions", headers=auth_headers).json()["suggestions"]
    by_id = {suggestion["suggestion_id"]: suggestion["status"] for suggestion in listed}

    assert response.status_code == 200
    assert by_id[old["suggestion_id"]] == "stale"
    assert by_id[new["suggestion_id"]] == "accepted"


def test_reject_does_not_change_plan_item_or_plan_hash(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    suggestion = create_suggestion(client, auth_headers, plan, plan["items"][0]["id"], monkeypatch, "ABP-123.mp4")

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/reject",
        headers=auth_headers,
        json={"reason_code": "user_rejected"},
    )
    stored = client.get(f"/api/plans/{plan['plan_id']}", headers=auth_headers).json()

    assert response.status_code == 200
    assert response.json()["suggestion"]["status"] == "rejected"
    assert stored["plan_hash"] == plan["plan_hash"]
    assert stored["items"][0]["target_name"] == plan["items"][0]["target_name"]


def test_accept_rejects_manual_edit_conflict(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item_id = plan["items"][0]["id"]
    patched = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{item_id}",
        headers=auth_headers,
        json={"target_name": "MAN-001.mp4"},
    ).json()
    suggestion = create_suggestion(client, auth_headers, patched, item_id, monkeypatch, "ABP-123.mp4")

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": patched["plan_hash"]},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "manual_edit_conflict"
