from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "avcleaner" / "desktop.py"


def test_desktop_starts_backend_before_importing_webview() -> None:
    source = DESKTOP.read_text(encoding="utf-8")

    server_start = source.index("subprocess.Popen")
    wait_for_server = source.index("_wait_for_server(args.host, port)")
    webview_import = source.index("import webview", server_start)

    assert server_start < wait_for_server < webview_import
    assert "server_start_timeout" in source
    assert "desktop-startup.log" in source


def test_desktop_gui_uses_no_window_server_subprocess() -> None:
    source = DESKTOP.read_text(encoding="utf-8")

    assert "def _server_command" in source
    assert '"--no-window"' in source
    assert '"--strict-port"' in source
    assert "server_process_started" in source
    assert "def _stop_server_process" in source
    assert "_stop_server_process(server_process)" in source


def test_desktop_gui_uses_edge_webview2_on_windows() -> None:
    source = DESKTOP.read_text(encoding="utf-8")

    assert 'sys.platform == "win32"' in source
    assert 'webview.start(_on_webview_start, gui="edgechromium")' in source
    assert "window_loaded" in source


def test_desktop_folder_bridge_is_exposed_after_window_start() -> None:
    source = DESKTOP.read_text(encoding="utf-8")

    assert "window.expose(bridge.choose_folder)" in source
    assert "bridge_exposed" in source
    assert "js_api=bridge" not in source
