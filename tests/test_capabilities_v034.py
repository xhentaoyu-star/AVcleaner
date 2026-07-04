from __future__ import annotations


def test_capabilities_exposes_v050_release_features(client) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.5.0"
    assert body["capabilities"]["manual_review"] is True
    assert body["capabilities"]["persisted_selection"] is True
    assert body["capabilities"]["plan_export"] is True
    assert body["capabilities"]["execution_summary"] is True
    assert body["capabilities"]["llm_payload_preview"] is True
    assert body["capabilities"]["llm_suggestion_review"] is True
    assert body["capabilities"]["llm_suggestion_cache"] is True
    assert body["capabilities"]["llm_accept_reject"] is True
    assert body["capabilities"]["llm_review_stability"] is True
    assert body["capabilities"]["legacy_llm_suggest_disabled"] is True
    assert body["capabilities"]["llm_cache_deterministic"] is True
    assert body["capabilities"]["packaging_ready"] is True
    assert body["capabilities"]["portable_mode"] is True
    assert body["capabilities"]["appdata_mode"] is True
    assert body["capabilities"]["health_check"] is True
