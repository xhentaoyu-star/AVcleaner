from __future__ import annotations


def test_diagnostics_summary_reports_human_fields_and_disabled_legacy_endpoints(client, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/diagnostics", headers=auth_headers)

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["version"] == "0.8.2"
    assert summary["runtime_mode"] in {"dev", "portable", "appdata"}
    assert summary["data_dir_writable"] in {True, False}
    assert summary["database_ok"] in {True, False}
    assert summary["templates_ok"] in {True, False}
    assert summary["static_ok"] in {True, False}
    assert summary["keyring_ok"] in {True, False}
    assert summary["legacy_execute_disabled"] is True
    assert summary["generic_llm_suggest_disabled"] is True
    assert summary["llm_configured"] in {True, False}
    assert summary["send_full_path_default"] is False


def test_diagnostics_panel_has_summary_and_collapsed_raw_json() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "avcleaner" / "templates" / "index.html").read_text(encoding="utf-8")
    js = (root / "avcleaner" / "static" / "app.js").read_text(encoding="utf-8")

    assert "diagnosticsSummary" in html
    assert "diagnosticsRawJson" in html
    assert "<details" in html
    assert "renderDiagnosticsSummary" in js
