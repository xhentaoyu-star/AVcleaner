from __future__ import annotations

from pathlib import Path

from .runtime import (
    ensure_runtime_dirs,
    runtime_data_dir,
    runtime_quarantine_fallback_dir,
)


def app_data_dir() -> Path:
    ensure_runtime_dirs()
    root = runtime_data_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return app_data_dir() / "avcleaner.db"


def quarantine_root() -> Path:
    ensure_runtime_dirs()
    root = runtime_quarantine_fallback_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_extension(value: str) -> str:
    ext = value.strip().lower()
    if not ext:
        return ""
    return ext if ext.startswith(".") else f".{ext}"


def resolve_for_compare(path: str | Path) -> str:
    return str(Path(path).resolve(strict=False)).rstrip("\\/")


def is_relative_to(child: str | Path, parent: str | Path) -> bool:
    child_resolved = Path(child).resolve(strict=False)
    parent_resolved = Path(parent).resolve(strict=False)
    try:
        child_resolved.relative_to(parent_resolved)
        return True
    except ValueError:
        return False


def safe_relative_path(path: str | Path, root: str | Path) -> str:
    try:
        return str(Path(path).resolve(strict=False).relative_to(Path(root).resolve(strict=False)))
    except ValueError:
        return Path(path).name
