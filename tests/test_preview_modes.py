from __future__ import annotations

from pathlib import Path

from conftest import make_file


def test_rule_preview_mode_combines_scan_and_plan(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")

    response = client.post(
        "/api/analyze",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "preview_mode": "rule"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scan"]["scan_id"]
    assert body["plan"]["plan_id"]
    assert body["plan"]["preview_mode"] == "rule"
    assert body["plan"]["llm_used"] is False
    assert body["plan"]["items"][0]["target_name"] == "ABP-123.mp4"


def test_ai_mode_hidden_from_capabilities_when_llm_not_configured(client) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["preview_modes"] == ["rule"]
    assert body["capabilities"]["ai_smart_preview"] is False
    assert body["capabilities"]["ai_preview_requires_llm_config"] is True
