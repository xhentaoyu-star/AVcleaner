from __future__ import annotations

import hashlib
from pathlib import Path

from .constants import JUNK_EXTENSIONS, SIDECAR_EXTENSIONS, VIDEO_EXTENSIONS
from .models import FileItem, ScanRequest, ScanResponse
from .paths import normalize_extension


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
        raise ValueError("扫描目录不存在")

    allowed_extensions = None
    if request.extensions:
        allowed_extensions = {normalize_extension(ext) for ext in request.extensions if normalize_extension(ext)}

    exclude_dirs = {name.lower() for name in (request.exclude_dirs or [])}
    files: list[FileItem] = []
    skipped_dirs: list[str] = []

    def should_skip_dir(path: Path) -> bool:
        if path == root:
            return False
        if path.name.lower() in exclude_dirs:
            skipped_dirs.append(str(path))
            return True
        if not request.include_hidden and path.name.startswith("."):
            skipped_dirs.append(str(path))
            return True
        return False

    iterator = root.rglob("*") if request.recursive else root.glob("*")
    for path in sorted(iterator, key=lambda p: str(p).lower()):
        if path.is_dir():
            continue
        if any(should_skip_dir(parent) for parent in path.parents if parent != root.parent):
            continue
        if not request.include_hidden and path.name.startswith("."):
            continue
        ext = normalize_extension(path.suffix)
        if allowed_extensions is not None and ext not in allowed_extensions:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(
            FileItem(
                id=file_id(path),
                path=str(path),
                relative_path=str(path.relative_to(root)),
                name=path.name,
                stem=path.stem,
                extension=ext,
                size=stat.st_size,
                mtime=stat.st_mtime,
                kind=classify_extension(ext),
                is_hidden=path.name.startswith("."),
            )
        )

    return ScanResponse(
        root_path=str(root),
        files=files,
        total_files=len(files),
        skipped_dirs=sorted(set(skipped_dirs)),
    )

