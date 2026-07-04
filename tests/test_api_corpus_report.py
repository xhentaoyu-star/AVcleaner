from __future__ import annotations

from avcleaner.database import connect
from avcleaner.rule_corpus import build_report


def db_counts() -> dict[str, int]:
    with connect() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in ["scans", "plans", "runs", "quarantine_manifests"]
        }


def test_corpus_report_requires_token(client) -> None:
    missing = client.get("/api/rules/corpus-report")
    wrong = client.get("/api/rules/corpus-report", headers={"X-AVCleaner-Token": "wrong"})

    assert missing.status_code == 401
    assert missing.json()["error_code"] == "api_token_missing"
    assert wrong.status_code == 403
    assert wrong.json()["error_code"] == "api_token_invalid"


def test_corpus_report_matches_shared_cli_logic(client, auth_headers: dict[str, str]) -> None:
    report = build_report()

    response = client.get("/api/rules/corpus-report", headers=auth_headers)

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["total_cases"] == report.total_cases
    assert summary["total_failures"] == report.total_failures
    assert summary["recognized_media_code_cases"] == report.recognized_media_code_cases
    assert summary["sidecar_cases"] == report.sidecar_cases
    assert summary["language_suffix_preservation_cases"] == report.language_suffix_cases
    assert summary["false_positive_failures"] == report.false_positive_failures


def test_corpus_report_endpoint_is_non_mutating(client, auth_headers: dict[str, str]) -> None:
    before = db_counts()

    response = client.get("/api/rules/corpus-report", headers=auth_headers)

    assert response.status_code == 200
    assert db_counts() == before


def test_corpus_report_failure_returns_stable_code(client, auth_headers: dict[str, str], monkeypatch) -> None:
    def fail_report():
        raise ValueError("malformed fixture")

    monkeypatch.setattr("avcleaner.app.build_corpus_report", fail_report)

    response = client.get("/api/rules/corpus-report", headers=auth_headers)

    assert response.status_code == 500
    assert response.json()["error_code"] == "corpus_report_failed"
