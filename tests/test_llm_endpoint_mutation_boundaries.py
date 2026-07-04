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


def counts() -> dict[str, int]:
    with connect() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in ("scans", "plans", "runs", "run_items", "quarantine_manifests", "llm_suggestions")
        }


def create_suggestion(client, headers: dict[str, str], plan: dict, item_id: str, monkeypatch: pytest.MonkeyPatch, name: str = "ABP-123.mp4") -> dict:
    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[
                LLMSuggestion(
                    item_id=item_id,
                    suggested_name=name,
                    media_code="ABP-123",
                    confidence=0.91,
                    reason="mock",
                )
            ]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=headers,
        json={"item_ids": [item_id], "include_neighbors": True, "use_cache": False},
    )
    assert response.status_code == 200
    return response.json()["suggestions"][0]


def test_payload_preview_and_list_do_not_mutate(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    before = counts()

    preview = client.post(
        f"/api/plans/{plan['plan_id']}/llm/payload-preview",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True},
    )
    listed = client.get(f"/api/plans/{plan['plan_id']}/llm/suggestions", headers=auth_headers)

    assert preview.status_code == 200
    assert listed.status_code == 200
    assert counts() == before


def test_suggest_creates_only_suggestion_records(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    media = make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    before = counts()

    suggestion = create_suggestion(client, auth_headers, plan, item["id"], monkeypatch)
    after = counts()
    stored_plan = client.get(f"/api/plans/{plan['plan_id']}", headers=auth_headers).json()

    assert suggestion["status"] == "valid"
    assert after["llm_suggestions"] == before["llm_suggestions"] + 1
    assert after["runs"] == before["runs"]
    assert after["run_items"] == before["run_items"]
    assert after["quarantine_manifests"] == before["quarantine_manifests"]
    assert stored_plan["items"][0]["target_name"] == item["target_name"]
    assert media.exists()


def test_accept_mutates_plan_and_suggestion_only(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    media = make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    suggestion = create_suggestion(client, auth_headers, plan, item["id"], monkeypatch)
    before = counts()

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": plan["plan_hash"]},
    )
    after = counts()

    assert response.status_code == 200
    assert after["scans"] == before["scans"]
    assert after["plans"] == before["plans"]
    assert after["llm_suggestions"] == before["llm_suggestions"]
    assert after["runs"] == before["runs"]
    assert after["run_items"] == before["run_items"]
    assert after["quarantine_manifests"] == before["quarantine_manifests"]
    assert media.exists()


def test_reject_mutates_suggestion_status_only(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    suggestion = create_suggestion(client, auth_headers, plan, item["id"], monkeypatch)
    before_plan = client.get(f"/api/plans/{plan['plan_id']}", headers=auth_headers).json()
    before = counts()

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/reject",
        headers=auth_headers,
        json={"reason_code": "user_rejected"},
    )
    after_plan = client.get(f"/api/plans/{plan['plan_id']}", headers=auth_headers).json()

    assert response.status_code == 200
    assert response.json()["suggestion"]["status"] == "rejected"
    assert counts() == before
    assert after_plan["plan_hash"] == before_plan["plan_hash"]
    assert after_plan["items"][0]["target_name"] == before_plan["items"][0]["target_name"]


def test_generic_llm_suggest_is_disabled_without_mutation(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    create_plan(client, auth_headers, tmp_path)
    before = counts()

    response = client.post(
        "/api/llm/suggest",
        headers=auth_headers,
        json={
            "items": [{"id": "x", "name": "ABP-123.mp4", "extension": ".mp4"}],
            "settings": {"provider": "ollama", "model": "mock-model"},
        },
    )

    assert response.status_code == 410
    assert response.json()["error_code"] == "legacy_llm_suggest_disabled"
    assert counts() == before
