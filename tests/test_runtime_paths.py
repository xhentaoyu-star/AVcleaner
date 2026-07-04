from __future__ import annotations

from pathlib import Path

from avcleaner import runtime


def test_env_data_dir_uses_dev_mode(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "state"
    monkeypatch.setenv("AVCLEANER_DATA_DIR", str(data_dir))
    monkeypatch.delenv("AVCLEANER_PORTABLE", raising=False)

    info = runtime.runtime_path_info(tmp_path / "app")

    assert info.mode == "dev"
    assert info.data_dir == data_dir
    assert info.logs_dir == data_dir / "logs"
    assert info.quarantine_dir == data_dir / "quarantine"


def test_portable_flag_uses_executable_directory_layout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVCLEANER_DATA_DIR", raising=False)
    monkeypatch.delenv("AVCLEANER_PORTABLE", raising=False)
    (tmp_path / "portable.flag").write_text("", encoding="utf-8")

    info = runtime.runtime_path_info(tmp_path)

    assert info.mode == "portable"
    assert info.data_dir == tmp_path / "data"
    assert info.logs_dir == tmp_path / "logs"
    assert info.quarantine_dir == tmp_path / "quarantine"


def test_portable_env_uses_executable_directory_layout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVCLEANER_DATA_DIR", raising=False)
    monkeypatch.setenv("AVCLEANER_PORTABLE", "1")

    info = runtime.runtime_path_info(tmp_path)

    assert info.mode == "portable"
    assert info.data_dir == tmp_path / "data"


def test_appdata_mode_uses_localappdata_on_windows_like_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVCLEANER_DATA_DIR", raising=False)
    monkeypatch.delenv("AVCLEANER_PORTABLE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))

    info = runtime.runtime_path_info(tmp_path / "app")

    assert info.mode == "appdata"
    assert str(info.data_dir).endswith("AVcleaner")


def test_choose_available_port_skips_occupied_port() -> None:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        occupied = int(sock.getsockname()[1])
        chosen = runtime.choose_available_port("127.0.0.1", occupied, attempts=3)

    assert chosen in {occupied + 1, occupied + 2}
