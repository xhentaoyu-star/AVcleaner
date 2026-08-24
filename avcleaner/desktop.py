from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

import uvicorn

from avcleaner.runtime import choose_available_port, is_loopback_host, runtime_logs_dir


class DesktopBridge:
    def __init__(self) -> None:
        self.window = None

    def choose_folder(self, initial_dir: str | None = None) -> dict:
        if self.window is None:
            return {"ok": False, "cancelled": True}
        import webview

        directory = Path(initial_dir or "").expanduser()
        if not directory.is_dir():
            directory = Path.home()
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG, directory=str(directory))
        if not result:
            return {"ok": False, "cancelled": True}
        path = result[0] if isinstance(result, (list, tuple)) else result
        return {"ok": True, "path": str(path)}


def _write_startup_log(message: str) -> None:
    try:
        log_dir = runtime_logs_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "desktop-startup.log").open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def _wait_for_server(host: str, port: int, *, timeout_seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    url = f"http://{host}:{port}/api/capabilities"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def _server_command(host: str, port: int, *, portable: bool, dev_allow_lan: bool) -> list[str]:
    if getattr(sys, "frozen", False):
        command = [sys.executable]
    else:
        command = [sys.executable, "-m", "avcleaner.desktop"]
    command.extend(["--no-window", "--strict-port", "--host", host, "--port", str(port)])
    if portable:
        command.append("--portable")
    if dev_allow_lan:
        command.append("--dev-allow-lan")
    return command


def _stop_server_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AVcleaner desktop wrapper.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--strict-port", action="store_true")
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--dev-allow-lan", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if not is_loopback_host(args.host):
        raise SystemExit("host_not_allowed: AVcleaner only binds to a loopback address")
    if args.portable:
        os.environ["AVCLEANER_PORTABLE"] = "1"

    _write_startup_log("desktop_start")
    port = args.port if args.strict_port else choose_available_port(args.host, args.port)
    _write_startup_log(f"port_selected:{port}")
    if args.no_window:
        from avcleaner.app import app as fastapi_app

        server = uvicorn.Server(
            uvicorn.Config(fastapi_app, host=args.host, port=port, log_level="warning", log_config=None, access_log=False)
        )
        server.run()
        return

    log_dir = runtime_logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    server_log = (log_dir / "desktop-server.log").open("a", encoding="utf-8")
    try:
        server_log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} server_process_launch\n")
        server_log.flush()
        server_process = subprocess.Popen(
            _server_command(args.host, port, portable=args.portable, dev_allow_lan=args.dev_allow_lan),
            stdout=server_log,
            stderr=server_log,
            close_fds=True,
        )
    finally:
        server_log.close()
    _write_startup_log(f"server_process_started:{server_process.pid}")
    if not _wait_for_server(args.host, port):
        exit_code = server_process.poll()
        if exit_code is not None:
            _write_startup_log(f"server_process_exited:{exit_code}")
        _stop_server_process(server_process)
        _write_startup_log("server_start_timeout:30")
        raise SystemExit("server_start_timeout")
    _write_startup_log("server_ready")

    import webview
    _write_startup_log("webview_imported")

    bridge = DesktopBridge()
    window = webview.create_window("AVcleaner", f"http://{args.host}:{port}", width=1440, height=900, min_size=(960, 700))
    bridge.window = window
    _write_startup_log("window_created")

    def _on_window_loaded() -> None:
        _write_startup_log("window_loaded")

    try:
        window.events.loaded += _on_window_loaded
    except Exception:
        _write_startup_log("window_loaded_hook_failed")

    def _on_webview_start() -> None:
        try:
            window.expose(bridge.choose_folder)
            _write_startup_log("bridge_exposed")
        except Exception:
            _write_startup_log("bridge_expose_failed")

    try:
        if sys.platform == "win32":
            webview.start(_on_webview_start, gui="edgechromium")
        else:
            webview.start(_on_webview_start)
    finally:
        _write_startup_log("webview_stopped")
        _stop_server_process(server_process)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            log_dir = runtime_logs_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "startup-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        raise
