from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .constants import JUNK_EXTENSIONS, SIDECAR_EXTENSIONS, VIDEO_EXTENSIONS
from .fingerprint import snapshot_for_path
from .models import ScanItem, ScanRequest, ScanResponse
from .paths import normalize_extension

QUARANTINE_DIR_NAME = ".avcleaner_quarantine"
RUNTIME_QUARANTINE_DIR_NAME = "quarantine"


def file_id(path: str | Path) -> str:
    return hashlib.sha1(str(path).encode("utf-8", errors="ignore")).hexdigest()[:16]


def classify_extension(ext: str) -> str:
    ext = normalize_extension(ext)
    if ext in VIDEO_EXTENSIONS:
        return "media"
    if ext in SIDECAR_EXTENSIONS:
        return "sidecar"
    if ext in JUNK_EXTENSIONS:
        return "junk"
    return "other"


def scan_files(request: ScanRequest) -> ScanResponse:
    root = Path(request.root_path).expanduser().resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise ValueError("scan_root_not_found")

    allowed_extensions = None
    if request.extensions:
        allowed_extensions = {normalize_extension(ext) for ext in request.extensions if normalize_extension(ext)}

    exclude_dirs = {name.lower() for name in (request.exclude_dirs or [])}
    exclude_dirs.add(QUARANTINE_DIR_NAME)
    exclude_dirs.add(RUNTIME_QUARANTINE_DIR_NAME)
    files: list[ScanItem] = []
    skipped_dirs: list[str] = []

    def walk_files(directory: Path):
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name.lower())
        except OSError:
            return
        for entry in entries:
            path = Path(entry.path)
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if is_dir:
                if entry.name.lower() in exclude_dirs or (not request.include_hidden and entry.name.startswith(".")):
                    skipped_dirs.append(str(path))
                elif request.recursive:
                    yield from walk_files(path)
                continue
            if entry.is_symlink() or (not request.include_hidden and entry.name.startswith(".")):
                continue
            yield path

    for path in walk_files(root):
        ext = normalize_extension(path.suffix)
        if allowed_extensions is not None and ext not in allowed_extensions:
            continue
        try:
            stat = path.stat()
            snapshot = snapshot_for_path(path)
        except OSError:
            continue
        files.append(
            ScanItem(
                id=file_id(path),
                path=str(path),
                relative_path=str(path.relative_to(root)),
                name=path.name,
                stem=path.stem,
                extension=ext,
                size=stat.st_size,
                mtime=stat.st_mtime,
                kind=classify_extension(ext),
                snapshot=snapshot,
                is_hidden=path.name.startswith("."),
            )
        )

    files.sort(key=lambda item: item.path.lower())
    return ScanResponse(
        root_path=str(root),
        files=files,
        total_files=len(files),
        skipped_dirs=sorted(set(skipped_dirs)),
    )
