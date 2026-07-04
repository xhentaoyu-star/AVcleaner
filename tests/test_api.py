from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from avcleaner.app import app


def test_api_scan_plan_execute_and_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AVCLEANER_DATA_DIR", str(tmp_path / "state"))
    video = tmp_path / "hhd800.com@ABP-123.mp4"
    video.write_bytes(b"video")
    client = TestClient(app)

    scan = client.post("/api/scan", json={"root_path": str(tmp_path), "recursive": True})
    assert scan.status_code == 200
    scan_payload = scan.json()
    assert scan_payload["total_files"] == 1

    plan = client.post(
        "/api/plan",
        json={"root_path": scan_payload["root_path"], "files": scan_payload["files"]},
    )
    assert plan.status_code == 200
    plan_payload = plan.json()
    assert plan_payload["items"][0]["suggested_name"] == "ABP-123.mp4"

    execute = client.post(
        "/api/execute",
        json={"root_path": scan_payload["root_path"], "items": plan_payload["items"], "confirm": True},
    )
    assert execute.status_code == 200
    assert (tmp_path / "ABP-123.mp4").exists()

    runs = client.get("/api/runs")
    assert runs.status_code == 200
    assert runs.json()

