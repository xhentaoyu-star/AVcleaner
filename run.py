from __future__ import annotations

import argparse
import os

import uvicorn

from avcleaner.runtime import choose_available_port


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AVcleaner web server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--portable", action="store_true")
    parser.add_argument("--strict-port", action="store_true")
    parser.add_argument("--dev-allow-lan", action="store_true")
    args = parser.parse_args()

    if args.host in {"0.0.0.0", "::"} and not args.dev_allow_lan:
        parser.error("host_not_allowed: use --dev-allow-lan to bind outside 127.0.0.1")
    if args.portable:
        os.environ["AVCLEANER_PORTABLE"] = "1"

    port = args.port if args.strict_port else choose_available_port(args.host, args.port)
    print(f"AVcleaner listening on http://{args.host}:{port}")
    uvicorn.run(
        "avcleaner.app:app",
        host=args.host,
        port=port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
