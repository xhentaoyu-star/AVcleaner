from __future__ import annotations

import os
import errno
from pathlib import Path
from typing import Callable

from .models import PlanItem, QuarantineManifest
from .paths import quarantine_root, safe_relative_path
from .repository import save_quarantine_manifest

ProgressCallback = Callable[[int, int], None]


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


def _move_file_with_progress(source: Path, target: Path, progress_callback: ProgressCallback | None = None) -> None:
    total = source.stat().st_size
    try:
        source.replace(target)
        if progress_callback:
            progress_callback(total, total)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise

    copied = 0
    copy_complete = False
    try:
        with source.open("rb") as src, target.open("xb") as dst:
            while True:
                chunk = src.read(8 * 1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
                copied += len(chunk)
                if progress_callback:
                    progress_callback(copied, total)
        copy_complete = True
        os.utime(target, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns))
        source.unlink()
    except Exception:
        if not copy_complete:
            target.unlink(missing_ok=True)
        raise


def quarantine_item(
    run_id: str,
    scan_root: Path,
    item: PlanItem,
    custom_dir: str = "",
    progress_callback: ProgressCallback | None = None,
) -> tuple[Path, QuarantineManifest]:
    source = Path(item.source_path).resolve(strict=False)
    root = choose_quarantine_root(scan_root, source, run_id, custom_dir)
    relative = safe_relative_path(source, scan_root)
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target = target.with_name(f"{target.stem}__duplicate_{run_id[:8]}{target.suffix}")
    _move_file_with_progress(source, target, progress_callback)
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
