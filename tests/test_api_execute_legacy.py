from __future__ import annotations

from pathlib import Path

from conftest import make_file


def test_legacy_execute_requires_token(client) -> None:
    response = client.post("/api/execute", json={"confirm": True, "items": []})

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_legacy_execute_returns_410_and_does_not_touch_files(tmp_path: Path, client, auth_headers) -> None:
    source = make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    target = tmp_path / "ABP-123.mp4"

    response = client.post(
        "/api/execute",
        json={
            "confirm": True,
            "root_path": str(tmp_path),
            "items": [
                {
                    "id": "forged",
                    "source_path": str(source),
                    "original_name": source.name,
                    "suggested_name": target.name,
                    "target_path": str(target),
                    "action": "rename",
                    "source": "manual",
                    "confidence": 1,
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 410
    assert response.json()["error_code"] == "legacy_execute_disabled"
    assert source.exists()
    assert not target.exists()
