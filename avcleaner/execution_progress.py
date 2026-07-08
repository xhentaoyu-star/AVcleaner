from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import Lock

from .database import utc_now_iso

TERMINAL_PROGRESS_STATES = {"success", "partial_success", "failed", "interrupted", "cancelled", "abandoned"}


@dataclass
class ExecutionProgress:
    run_id: str
    plan_id: str = ""
    state: str = "running"
    phase: str = "starting"
    message: str = "starting"
    total_items: int = 0
    completed_items: int = 0
    current_item_id: str = ""
    current_item_name: str = ""
    current_operation: str = ""
    current_bytes: int = 0
    total_bytes: int = 0
    error_code: str = ""
    started_at: str = ""
    updated_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["file_percent"] = round((self.current_bytes / self.total_bytes) * 100, 1) if self.total_bytes else 0.0
        payload["overall_percent"] = round((self.completed_items / self.total_items) * 100, 1) if self.total_items else 0.0
        payload["terminal"] = self.state in TERMINAL_PROGRESS_STATES
        return payload


_LOCK = Lock()
_PROGRESS: dict[str, ExecutionProgress] = {}


def start_progress(run_id: str, plan_id: str, total_items: int = 0) -> dict:
    now = utc_now_iso()
    progress = ExecutionProgress(
        run_id=run_id,
        plan_id=plan_id,
        total_items=total_items,
        started_at=now,
        updated_at=now,
    )
    with _LOCK:
        _PROGRESS[run_id] = progress
        return progress.to_dict()


def update_progress(run_id: str, **changes) -> dict:
    now = utc_now_iso()
    with _LOCK:
        progress = _PROGRESS.get(run_id) or ExecutionProgress(run_id=run_id, started_at=now)
        for key, value in changes.items():
            if hasattr(progress, key):
                setattr(progress, key, value)
        progress.updated_at = now
        if progress.state in TERMINAL_PROGRESS_STATES and not progress.completed_at:
            progress.completed_at = now
        _PROGRESS[run_id] = progress
        return progress.to_dict()


def start_item(
    run_id: str,
    *,
    item_id: str,
    item_name: str,
    operation: str,
    completed_items: int,
    total_items: int,
) -> dict:
    return update_progress(
        run_id,
        state="running",
        phase=operation,
        message="processing_item",
        total_items=total_items,
        completed_items=completed_items,
        current_item_id=item_id,
        current_item_name=item_name,
        current_operation=operation,
        current_bytes=0,
        total_bytes=0,
        error_code="",
    )


def update_file_progress(run_id: str, copied_bytes: int, total_bytes: int, message: str = "moving_file") -> dict:
    return update_progress(
        run_id,
        phase="quarantine",
        message=message,
        current_bytes=max(0, int(copied_bytes)),
        total_bytes=max(0, int(total_bytes)),
    )


def complete_item(run_id: str, completed_items: int, total_items: int, message: str = "item_done") -> dict:
    return update_progress(
        run_id,
        message=message,
        completed_items=completed_items,
        total_items=total_items,
        current_bytes=0,
        total_bytes=0,
    )


def finish_progress(run_id: str, state: str, summary: dict[str, int] | None = None, error_code: str = "") -> dict:
    return update_progress(
        run_id,
        state=state,
        phase="done",
        message="execution_done",
        error_code=error_code,
        completed_items=sum((summary or {}).values()) if summary else 0,
    )


def get_progress(run_id: str) -> dict | None:
    with _LOCK:
        progress = _PROGRESS.get(run_id)
        return progress.to_dict() if progress else None
