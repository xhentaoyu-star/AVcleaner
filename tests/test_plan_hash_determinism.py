from __future__ import annotations

from pathlib import Path

from avcleaner.models import PlanRequest, ScanRequest, RuleTraceStep
from avcleaner.planner import compute_plan_hash, create_plan
from avcleaner.repository import create_scan
from avcleaner.scanner import scan_files


def persisted_plan(tmp_path: Path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "hhd800.com@FC2-PPV-4856696_1.mp4").write_bytes(b"video")
    scan = create_scan(ScanRequest(root_path=str(root)), scan_files(ScanRequest(root_path=str(root))))
    return create_plan(PlanRequest(scan_id=scan.scan_id))


def test_same_scan_same_settings_same_rule_output_has_same_plan_hash(tmp_path: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    (root / "ABP-123.mp4").write_bytes(b"video")
    scan = create_scan(ScanRequest(root_path=str(root)), scan_files(ScanRequest(root_path=str(root))))

    first = create_plan(PlanRequest(scan_id=scan.scan_id))
    second = create_plan(PlanRequest(scan_id=scan.scan_id))

    assert first.plan_hash == second.plan_hash


def test_changing_target_name_changes_plan_hash(tmp_path: Path) -> None:
    plan = persisted_plan(tmp_path)
    item = plan.items[0]
    changed = item.model_copy(update={"target_name": "FC2-PPV-4856696-2.mp4", "suggested_name": "FC2-PPV-4856696-2.mp4"})

    assert compute_plan_hash([item]) != compute_plan_hash([changed])


def test_changing_trace_changes_plan_hash(tmp_path: Path) -> None:
    plan = persisted_plan(tmp_path)
    item = plan.items[0]
    changed_trace = [step.model_copy(update={"warnings": ["trace_changed"]}) if index == 0 else step for index, step in enumerate(item.trace)]
    changed = item.model_copy(update={"trace": changed_trace})

    assert compute_plan_hash([item]) != compute_plan_hash([changed])


def test_trace_dict_key_order_does_not_change_plan_hash(tmp_path: Path) -> None:
    plan = persisted_plan(tmp_path)
    item = plan.items[0]
    reordered = [
        RuleTraceStep.model_validate(
            {
                "warnings": list(step.warnings),
                "confidence_delta": step.confidence_delta,
                "preserved_tokens": list(step.preserved_tokens),
                "removed_tokens": list(step.removed_tokens),
                "after": step.after,
                "before": step.before,
                "rule_id": step.rule_id,
            }
        )
        for step in item.trace
    ]

    assert compute_plan_hash([item]) == compute_plan_hash([item.model_copy(update={"trace": reordered})])
