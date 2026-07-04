from __future__ import annotations

import threading
import argparse
import os
import traceback

import uvicorn

from avcleaner.runtime import choose_available_port, runtime_logs_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AVcleaner desktop wrapper.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--strict-port", action="store_true")
    parser.add_argument("--no-window", action="store_true")
    parser.add_argument("--dev-allow-lan", action="store_true")
    args = parser.parse_args()

    if args.host in {"0.0.0.0", "::"} and not args.dev_allow_lan:
        raise SystemExit("host_not_allowed: use --dev-allow-lan to bind outside 127.0.0.1")
    if args.portable:
        os.environ["AVCLEANER_PORTABLE"] = "1"

    port = args.port if args.strict_port else choose_available_port(args.host, args.port)
    from avcleaner.app import app as fastapi_app

    server = uvicorn.Server(
        uvicorn.Config(fastapi_app, host=args.host, port=port, log_level="warning", log_config=None, access_log=False)
    )
    if args.no_window:
        server.run()
        return

    import webview

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    webview.create_window("AVcleaner", f"http://{args.host}:{port}", width=1280, height=820)
    webview.start()


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
