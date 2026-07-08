from __future__ import annotations

from avcleaner.enums import Operation, RunItemState, RunState
from avcleaner.models import ExecutionItem, ExecutionRun
from avcleaner.repository import create_run, get_run, get_run_items, mark_interrupted_runs, upsert_run_item


def test_mark_interrupted_runs_fails_pending_items_and_refreshes_summary() -> None:
    run = create_run(ExecutionRun(run_id="run_recovery_contract", state=RunState.RUNNING, summary={}))
    upsert_run_item(
        ExecutionItem(
            id="runitem_done",
            run_id=run.run_id,
            plan_item_id="item_done",
            operation=Operation.RENAME,
            state=RunItemState.RENAMED,
            source_path="L:/source-a.mp4",
            target_path="L:/target-a.mp4",
        )
    )
    upsert_run_item(
        ExecutionItem(
            id="runitem_pending",
            run_id=run.run_id,
            plan_item_id="item_pending",
            operation=Operation.QUARANTINE,
            state=RunItemState.PENDING,
            source_path="L:/source-b.xltd",
            target_path="L:/source-b.xltd",
        )
    )

    assert mark_interrupted_runs() == 1

    recovered = get_run(run.run_id)
    items = {item.id: item for item in get_run_items(run.run_id)}
    assert recovered.state == RunState.INTERRUPTED
    assert recovered.completed_at
    assert recovered.rollback_available is True
    assert recovered.summary == {"failed": 1, "renamed": 1}
    assert items["runitem_pending"].state == RunItemState.FAILED
    assert items["runitem_pending"].message == "operation_interrupted"
    assert items["runitem_pending"].issue_code == "operation_interrupted"
