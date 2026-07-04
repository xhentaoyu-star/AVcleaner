from __future__ import annotations

import os
from pathlib import Path


def app_data_dir() -> Path:
    override = os.environ.get("AVCLEANER_DATA_DIR")
    if override:
        root = Path(override)
    elif os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA")
        root = Path(local_appdata) / "AVcleaner" if local_appdata else Path.home() / "AppData" / "Local" / "AVcleaner"
    else:
        root = Path.home() / ".local" / "share" / "avcleaner"
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return app_data_dir() / "avcleaner.db"


def quarantine_root() -> Path:
    root = app_data_dir() / "quarantine"
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

