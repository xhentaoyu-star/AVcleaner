from __future__ import annotations

import json
from pathlib import Path

from avcleaner.database import connect
from avcleaner.models import PlanRequest, ScanRequest
from avcleaner.planner import create_plan
from avcleaner.repository import create_scan, get_plan
from avcleaner.scanner import scan_files


def test_planner_persists_rule_trace_json(tmp_path: Path) -> None:
    (tmp_path / "hhd800.com@FC2-PPV-4856696_1.mp4").write_bytes(b"video")
    scan = create_scan(ScanRequest(root_path=str(tmp_path)), scan_files(ScanRequest(root_path=str(tmp_path))))

    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    stored = get_plan(plan.plan_id)

    assert stored.items[0].trace
    with connect() as conn:
        row = conn.execute("SELECT trace_json FROM plan_items WHERE plan_id = ?", (plan.plan_id,)).fetchone()
    trace = json.loads(row["trace_json"])
    assert trace
    assert trace[-1]["after"] == stored.items[0].suggested_name


def test_plan_hash_changes_when_trace_changes(tmp_path: Path) -> None:
    (tmp_path / "ABP-123.mp4").write_bytes(b"video")
    scan = create_scan(ScanRequest(root_path=str(tmp_path)), scan_files(ScanRequest(root_path=str(tmp_path))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    item = plan.items[0]

    mutated = item.model_copy(update={"trace": [step.model_copy(update={"warnings": ["trace_changed"]}) for step in item.trace]})
    from avcleaner.planner import compute_plan_hash

    assert compute_plan_hash([item]) != compute_plan_hash([mutated])
