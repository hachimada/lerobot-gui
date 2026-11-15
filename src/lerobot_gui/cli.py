"""`lerobot-gui` command."""

from __future__ import annotations

import argparse
import threading
import webbrowser

from .paths import tilde
from .settings import DEFAULT_PORT, Settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lerobot-gui", description="Local web GUI for the lerobot commands.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--root", help="lerobot workspace to run the commands in (default: current directory)")
    parser.add_argument("--no-open", action="store_true", help="don't open a browser tab")
    args = parser.parse_args(argv)

    import uvicorn

    from .app import create_app

    s = Settings.from_env(root=args.root, port=args.port)
    url = f"http://{s.host}:{s.port}/"
    print(f"LeRobot GUI: {url}  (root={tilde(s.root)}, HF_LEROBOT_HOME={tilde(s.hf_home)})")
    if not args.no_open:
        threading.Timer(1.2, webbrowser.open, [url]).start()
    uvicorn.run(create_app(s), host=s.host, port=s.port, log_level="warning")
