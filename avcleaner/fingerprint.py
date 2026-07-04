from __future__ import annotations

import hashlib
from pathlib import Path

from .models import FileSnapshot

CHUNK_SIZE = 1024 * 1024


def quick_fingerprint(path: Path, size: int, modified_ns: int) -> str:
    if size == 0:
        return f"empty:{modified_ns}"
    hasher = hashlib.sha256()
    hasher.update(str(size).encode("ascii"))
    hasher.update(str(modified_ns).encode("ascii"))
    with path.open("rb") as handle:
        if size <= CHUNK_SIZE:
            hasher.update(handle.read())
        elif size <= CHUNK_SIZE * 2:
            hasher.update(handle.read())
        else:
            hasher.update(handle.read(CHUNK_SIZE))
            handle.seek(max(0, size - CHUNK_SIZE))
            hasher.update(handle.read(CHUNK_SIZE))
    return hasher.hexdigest()


def snapshot_for_path(path: Path) -> FileSnapshot:
    stat = path.stat()
    return FileSnapshot(
        size=stat.st_size,
        created_ns=getattr(stat, "st_ctime_ns", int(stat.st_ctime * 1_000_000_000)),
        modified_ns=getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)),
        fingerprint=quick_fingerprint(path, stat.st_size, getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
    )
