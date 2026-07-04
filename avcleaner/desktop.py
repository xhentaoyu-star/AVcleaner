from __future__ import annotations

import socket
import threading

import uvicorn


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    import webview

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config("avcleaner.app:app", host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    webview.create_window("AVcleaner", f"http://127.0.0.1:{port}", width=1280, height=820)
    webview.start()


if __name__ == "__main__":
    main()

