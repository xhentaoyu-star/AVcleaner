from __future__ import annotations

import errno
import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .models import PlanItem, QuarantineManifest
from .paths import quarantine_root, safe_relative_path
from .repository import save_quarantine_manifest

ProgressCallback = Callable[[int, int], None]
COPY_CHUNK_SIZE = 8 * 1024 * 1024


class QuarantineRecoveryRequired(OSError):
    def __init__(self, target_path: Path) -> None:
        super().__init__("quarantine_recovery_required")
        self.target_path = target_path


class QuarantinePathError(OSError):
    code = "quarantine_inside_scan_root"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True)
class QuarantineBaseStatus:
    configured_dir: str
    effective_dir: Path
    using_default: bool
    fallback_active: bool
    writable: bool


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


def resolve_quarantine_base(custom_dir: str = "") -> QuarantineBaseStatus:
    configured_dir = str(custom_dir or "").strip()
    preferred = _configured_quarantine_base(configured_dir)
    if _is_writable_dir(preferred):
        return QuarantineBaseStatus(
            configured_dir=configured_dir,
            effective_dir=preferred,
            using_default=not configured_dir,
            fallback_active=False,
            writable=True,
        )

    fallback = quarantine_root()
    return QuarantineBaseStatus(
        configured_dir=configured_dir,
        effective_dir=fallback,
        using_default=not configured_dir,
        fallback_active=bool(configured_dir),
        writable=_is_writable_dir(fallback),
    )


def choose_quarantine_root(scan_root: Path, source_path: Path, run_id: str, custom_dir: str = "") -> Path:
    resolved_scan_root = scan_root.resolve(strict=False)
    configured_dir = str(custom_dir or "").strip()
    if configured_dir:
        configured_base = _configured_quarantine_base(configured_dir).resolve(strict=False)
        if configured_base == resolved_scan_root or configured_base.is_relative_to(resolved_scan_root):
            raise QuarantinePathError()

    effective_base = resolve_quarantine_base(custom_dir).effective_dir.resolve(strict=False)
    if effective_base == resolved_scan_root or effective_base.is_relative_to(resolved_scan_root):
        raise QuarantinePathError()

    preferred = effective_base / run_id
    if _is_writable_dir(preferred):
        return preferred

    fallback = quarantine_root() / run_id
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(COPY_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_then_delete_verified(
    source: Path,
    target: Path,
    progress_callback: ProgressCallback | None = None,
) -> None:
    source_stat = source.stat()
    total = source_stat.st_size
    temp = target.with_name(f".{target.name}.avcleaner-copy-{uuid.uuid4().hex}.tmp")
    copied = 0
    source_digest = hashlib.sha256()
    finalized = False
    try:
        with source.open("rb") as src, temp.open("xb") as dst:
            while True:
                chunk = src.read(COPY_CHUNK_SIZE)
                if not chunk:
                    break
                written = dst.write(chunk)
                if written != len(chunk):
                    raise OSError("quarantine_copy_incomplete")
                source_digest.update(chunk)
                copied += len(chunk)
                if progress_callback:
                    progress_callback(copied, total)
            dst.flush()
            os.fsync(dst.fileno())

        current_source_stat = source.stat()
        if current_source_stat.st_size != source_stat.st_size or current_source_stat.st_mtime_ns != source_stat.st_mtime_ns:
            raise OSError("quarantine_source_changed_during_copy")
        if copied != total or temp.stat().st_size != total:
            raise OSError("quarantine_copy_size_mismatch")
        if _sha256_file(temp) != source_digest.hexdigest():
            raise OSError("quarantine_copy_hash_mismatch")

        os.utime(temp, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        if target.exists():
            raise FileExistsError(target)
        temp.rename(target)
        finalized = True
        source.unlink()
    except Exception:
        temp.unlink(missing_ok=True)
        if finalized and source.exists():
            target.unlink(missing_ok=True)
        raise


def move_file_verified(source: Path, target: Path, progress_callback: ProgressCallback | None = None) -> None:
    total = source.stat().st_size
    if target.exists():
        raise FileExistsError(target)
    try:
        source.rename(target)
        if progress_callback:
            progress_callback(total, total)
        return
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise

    _copy_then_delete_verified(source, target, progress_callback)


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
    move_file_verified(source, target, progress_callback)
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
    try:
        save_quarantine_manifest(manifest)
    except Exception:
        try:
            move_file_verified(target, source)
        except Exception as recovery_error:
            raise QuarantineRecoveryRequired(target) from recovery_error
        raise
    return target, manifest
