from __future__ import annotations


def test_capabilities_exposes_v070_release_features(client) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.8.0"
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
    assert body["capabilities"]["release_zip"] is True
    assert body["capabilities"]["artifact_manifest"] is True
    assert body["capabilities"]["packaged_temp_execution_smoke"] is True
    assert body["capabilities"]["portable_mode"] is True
    assert body["capabilities"]["appdata_mode"] is True
    assert body["capabilities"]["health_check"] is True
    assert body["capabilities"]["llm_provider_compatibility_modes"] is True
    assert body["capabilities"]["llm_prompt_json_compat"] is True
    assert body["capabilities"]["llm_strict_schema_fixed"] is True
    assert body["capabilities"]["llm_error_taxonomy"] is True
    assert body["capabilities"]["legacy_execute_disabled"] is True
    assert body["capabilities"]["beta_ux_polish"] is True
    assert body["capabilities"]["diagnostics_panel"] is True
    assert body["capabilities"]["first_run_helper"] is True
    assert body["capabilities"]["ui_error_explanations"] is True
    assert body["capabilities"]["run_detail"] is True
    assert body["capabilities"]["rollback_preview"] is True
    assert body["capabilities"]["run_export"] is True
    assert body["capabilities"]["recent_folders"] is True
    assert body["capabilities"]["execution_report"] is True
    assert body["capabilities"]["configurable_quarantine_dir"] is True
    assert body["capabilities"]["ui_polish_072"] is True
    assert body["capabilities"]["icon_system"] is True
    assert body["capabilities"]["tabler_icon_subset"] is True
    assert body["capabilities"]["icon_registry"] is True
    assert body["capabilities"]["toast_feedback"] is True
    assert body["capabilities"]["detail_drawer"] is True
    assert body["capabilities"]["responsive_table"] is True
    assert body["capabilities"]["fixed_workbench_layout"] is True
    assert body["capabilities"]["desktop_window_baseline"] is True
    assert body["capabilities"]["right_detail_stack"] is True
    assert body["capabilities"]["compact_execution_module"] is True
    assert body["capabilities"]["workbench_visual_redesign"] is True
    assert body["capabilities"]["simple_ui_mode"] is True
    assert body["capabilities"]["debug_ui_mode"] is True
    assert body["capabilities"]["progressive_disclosure"] is True
