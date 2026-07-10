from __future__ import annotations

from avcleaner import execution_progress


def test_completed_progress_records_are_bounded() -> None:
    execution_progress._PROGRESS.clear()

    for index in range(execution_progress.MAX_PROGRESS_ENTRIES + 25):
        run_id = f"run-{index:04d}"
        execution_progress.start_progress(run_id, "plan")
        execution_progress.finish_progress(run_id, "success")

    assert len(execution_progress._PROGRESS) <= execution_progress.MAX_PROGRESS_ENTRIES
    assert execution_progress.get_progress(f"run-{execution_progress.MAX_PROGRESS_ENTRIES + 24:04d}") is not None
