from __future__ import annotations

from avcleaner.database import connect


def db_counts() -> dict[str, int]:
    with connect() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in ["scans", "plans", "runs", "quarantine_manifests"]
        }


def test_rules_test_returns_sidecar_language_trace(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "FC2-PPV-4856696_1.zh-CN.srt"})

    assert response.status_code == 200
    suggestion = response.json()["suggestion"]
    assert suggestion["suggested_name"] == "FC2PPV-4856696-1.zh-CN.srt"
    assert suggestion["media_code"] == "FC2PPV-4856696"
    assert suggestion["part_suffix"] == "-1"
    assert suggestion["variant"] == ""
    assert suggestion["language_suffix"] == "zh-CN"
    assert any(step["rule_id"] == "detect_sidecar_language" for step in suggestion["trace"])
    assert any(step["rule_id"] == "preserve_sidecar_language" for step in suggestion["trace"])
    assert response.json()["validation_preview"] == []


def test_rules_test_sidecar_case_remains_non_mutating(client, auth_headers: dict[str, str]) -> None:
    before = db_counts()

    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "[ad] ABP123.chs.ass"})

    assert response.status_code == 200
    assert db_counts() == before
