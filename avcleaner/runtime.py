from __future__ import annotations

import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

APP_DIR_NAME = "AVcleaner"
RuntimeMode = Literal["dev", "portable", "appdata"]


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def portable_flag_path(base_dir: Path | None = None) -> Path:
    return (base_dir or executable_dir()) / "portable.flag"


def runtime_mode(base_dir: Path | None = None) -> RuntimeMode:
    if os.environ.get("AVCLEANER_DATA_DIR"):
        return "dev"
    if _truthy(os.environ.get("AVCLEANER_PORTABLE")) or portable_flag_path(base_dir).exists():
        return "portable"
    return "appdata"


def _appdata_root() -> Path:
    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / APP_DIR_NAME
        return Path.home() / "AppData" / "Local" / APP_DIR_NAME
    return Path.home() / ".local" / "share" / "avcleaner"


def runtime_data_dir(base_dir: Path | None = None) -> Path:
    override = os.environ.get("AVCLEANER_DATA_DIR")
    if override:
        return Path(override)
    if runtime_mode(base_dir) == "portable":
        return (base_dir or executable_dir()) / "data"
    return _appdata_root()


def runtime_logs_dir(base_dir: Path | None = None) -> Path:
    if runtime_mode(base_dir) == "portable" and not os.environ.get("AVCLEANER_DATA_DIR"):
        return (base_dir or executable_dir()) / "logs"
    return runtime_data_dir(base_dir) / "logs"


def runtime_quarantine_fallback_dir(base_dir: Path | None = None) -> Path:
    if runtime_mode(base_dir) == "portable" and not os.environ.get("AVCLEANER_DATA_DIR"):
        return (base_dir or executable_dir()) / "quarantine"
    return runtime_data_dir(base_dir) / "quarantine"


def ensure_runtime_dirs(base_dir: Path | None = None) -> None:
    for path in (runtime_data_dir(base_dir), runtime_logs_dir(base_dir), runtime_quarantine_fallback_dir(base_dir)):
        path.mkdir(parents=True, exist_ok=True)


def directory_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".avcleaner_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def choose_available_port(host: str, preferred_port: int, *, attempts: int = 20) -> int:
    for port in range(preferred_port, preferred_port + attempts):
        if is_port_available(host, port):
            return port
    raise RuntimeError("port_unavailable")


@dataclass(frozen=True)
class RuntimePathInfo:
    mode: RuntimeMode
    data_dir: Path
    logs_dir: Path
    quarantine_dir: Path
    portable_flag: Path


def runtime_path_info(base_dir: Path | None = None) -> RuntimePathInfo:
    mode = runtime_mode(base_dir)
    return RuntimePathInfo(
        mode=mode,
        data_dir=runtime_data_dir(base_dir),
        logs_dir=runtime_logs_dir(base_dir),
        quarantine_dir=runtime_quarantine_fallback_dir(base_dir),
        portable_flag=portable_flag_path(base_dir),
    )
