from __future__ import annotations

import os
import shutil
from pathlib import Path

from .models import PlanItem, QuarantineManifest
from .paths import quarantine_root, safe_relative_path
from .repository import save_quarantine_manifest


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _configured_quarantine_base(custom_dir: str = "") -> Path:
    cleaned = str(custom_dir or "").strip()
    if cleaned:
        return Path(os.path.expandvars(cleaned)).expanduser()
    return quarantine_root()


def choose_quarantine_root(scan_root: Path, source_path: Path, run_id: str, custom_dir: str = "") -> Path:
    preferred = _configured_quarantine_base(custom_dir) / run_id
    if _is_writable_dir(preferred):
        return preferred

    fallback = quarantine_root() / run_id
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def quarantine_item(run_id: str, scan_root: Path, item: PlanItem, custom_dir: str = "") -> tuple[Path, QuarantineManifest]:
    source = Path(item.source_path).resolve(strict=False)
    root = choose_quarantine_root(scan_root, source, run_id, custom_dir)
    relative = safe_relative_path(source, scan_root)
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target = target.with_name(f"{target.stem}__duplicate_{run_id[:8]}{target.suffix}")
    shutil.move(str(source), str(target))
    snapshot = item.snapshot
    manifest = QuarantineManifest(
        run_id=run_id,
        item_id=item.id,
        original_abs_path=str(source),
        original_rel_path=relative,
        quarantine_abs_path=str(target),
        size=snapshot.size if snapshot else item.size,
        created_ns=snapshot.created_ns if snapshot else 0,
        modified_ns=snapshot.modified_ns if snapshot else 0,
        reason=item.reason,
        restore_status="available",
    )
    save_quarantine_manifest(manifest)
    return target, manifest
