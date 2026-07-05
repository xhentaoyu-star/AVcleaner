from __future__ import annotations

import sys
import types
from pathlib import Path

from avcleaner.desktop import DesktopBridge


class FakeWindow:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def create_file_dialog(self, dialog_type, directory):
        self.calls.append((dialog_type, directory))
        return self.result


def test_desktop_bridge_choose_folder_returns_selected_folder(monkeypatch, tmp_path: Path) -> None:
    fake_webview = types.SimpleNamespace(FOLDER_DIALOG="folder")
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    bridge = DesktopBridge()
    window = FakeWindow([str(tmp_path)])
    bridge.window = window

    response = bridge.choose_folder(str(tmp_path))

    assert response == {"ok": True, "path": str(tmp_path)}
    assert window.calls == [("folder", str(tmp_path))]


def test_desktop_bridge_choose_folder_cancel(monkeypatch, tmp_path: Path) -> None:
    fake_webview = types.SimpleNamespace(FOLDER_DIALOG="folder")
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    bridge = DesktopBridge()
    bridge.window = FakeWindow(None)

    response = bridge.choose_folder(str(tmp_path))

    assert response == {"ok": False, "cancelled": True}
