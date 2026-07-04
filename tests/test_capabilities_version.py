from __future__ import annotations


def test_capabilities_exposes_v061_release_candidate_flags(client) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.6.1"
    assert body["capabilities"]["beta_ux_polish"] is True
    assert body["capabilities"]["diagnostics_panel"] is True
    assert body["capabilities"]["first_run_helper"] is True
    assert body["capabilities"]["ui_error_explanations"] is True
    assert body["capabilities"]["release_candidate_polish"] is True
    assert body["capabilities"]["ui_explanation_coverage"] is True
    assert body["capabilities"]["diagnostics_summary"] is True
    assert body["capabilities"]["quarantine_reason_explanations"] is True
    assert body["capabilities"]["legacy_execute_disabled"] is True
    assert body["capabilities"]["legacy_llm_suggest_disabled"] is True
