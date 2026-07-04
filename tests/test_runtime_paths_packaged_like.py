from __future__ import annotations

from pathlib import Path

from avcleaner import runtime


def test_portable_paths_support_spaces_and_non_ascii(tmp_path: Path, monkeypatch) -> None:
    app_dir = tmp_path / "AVcleaner Portable 测试"
    app_dir.mkdir()
    (app_dir / "portable.flag").write_text("", encoding="utf-8")
    monkeypatch.delenv("AVCLEANER_DATA_DIR", raising=False)
    monkeypatch.delenv("AVCLEANER_PORTABLE", raising=False)

    info = runtime.runtime_path_info(app_dir)

    assert info.mode == "portable"
    assert info.data_dir == app_dir / "data"
    assert runtime.directory_writable(info.data_dir) is True


def test_appdata_mode_does_not_use_packaged_directory_without_portable_flag(tmp_path: Path, monkeypatch) -> None:
    app_dir = tmp_path / "AVcleaner"
    local_appdata = tmp_path / "Local AppData"
    app_dir.mkdir()
    monkeypatch.delenv("AVCLEANER_DATA_DIR", raising=False)
    monkeypatch.delenv("AVCLEANER_PORTABLE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))

    info = runtime.runtime_path_info(app_dir)

    assert info.mode == "appdata"
    assert info.data_dir == local_appdata / "AVcleaner"
    assert app_dir not in info.data_dir.parents
