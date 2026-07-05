from __future__ import annotations

from pathlib import Path


def make_file(root: Path, name: str, content: bytes = b"video") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def create_scan_and_plan(client, headers: dict[str, str], root: Path) -> tuple[dict, dict]:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return scan.json(), plan.json()


def create_executed_run(client, headers: dict[str, str], root: Path, filename: str = "hhd800.com@ABP-123.mp4") -> dict:
    make_file(root, filename)
    scan, plan = create_scan_and_plan(client, headers, root)
    selected = [
        item["id"]
        for item in plan["items"]
        if item["checked"] and item["action"] in {"rename", "quarantine"}
    ]
    assert selected
    execute = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json={"selected_item_ids": selected, "confirm": True, "plan_hash": plan["plan_hash"]},
        headers=headers,
    )
    assert execute.status_code == 200
    return {"scan": scan, "plan": plan, "execute": execute.json()}
