"""Serve the GUI on a fake machine for the browser tests (frontend/e2e, `npm run e2e`).

Everything is fake: /dev and /sys, the workspace and the lerobot commands (tests/fakes.py).
The arm check is stubbed too: the fake ports have real names (/dev/ttyACM0...), and the real
check would open whatever is plugged into this PC. So are the Hub, the account (a made-up
`alice`) and the Hugging Face cache: nothing reaches the network, this machine's Hugging Face
credentials or its caches.

    python -m tests.e2e.serve --port 7899
"""

from __future__ import annotations

import argparse
import contextlib
import os
import tempfile
from pathlib import Path

import uvicorn

from lerobot_gui.adapters import accounts, environment, hub, torch_devices
from lerobot_gui.app import create_app
from lerobot_gui.jobs import JobManager
from lerobot_gui.settings import Settings

from .. import netguard
from ..fakes import (
    arm_result,
    calibration_folders,
    fake_serial_ports,
    make_bin_dir,
    make_fs_root,
    make_hub_cache,
    make_workspace,
)


def arms_ok(arms: list[dict]) -> dict:
    return {"arms": [arm_result(a, "ok") for a in arms], "swapped": False}


def hub_models(author: str, token: bool | None) -> list[dict]:
    names = ["smolvla_base", "pi05_base", "pi0_base", "xvla-base", "pi0fast-base"] if author == "lerobot" else []
    return [
        {"id": f"{author}/{n}", "downloads": 1000 - i, "likes": 0, "created": "2025-06-01", "private": False}
        for i, n in enumerate(names)
    ]


def fake_services() -> None:
    """A made-up Hugging Face account; logging in or out is refused (it would write real
    credentials). The Hub's listings are made up too."""

    def refuse(*_args) -> dict:
        raise ValueError("The browser tests don't log in or out.")

    accounts.hf_status = lambda refresh=False: {"logged_in": True, "user": "alice", "orgs": ["lab"]}
    accounts.hf_login = refuse
    accounts.hf_logout = refuse
    hub.fetch_repos = lambda owner: {
        "datasets": [{"id": f"{owner}/pick-demo", "private": owner == "lab", "downloads": 3, "likes": 0,
                      "updated": "2026-01-05T09:30:00+00:00",
                      "url": f"https://huggingface.co/datasets/{owner}/pick-demo"}],
        "models": [{"id": f"{owner}/act-pick", "private": False, "downloads": 1, "likes": 0,
                    "updated": "2026-01-06T10:15:00+00:00",
                    "url": f"https://huggingface.co/{owner}/act-pick"}],
    }  # fmt: skip


def warm_up() -> None:
    """Build lerobot's option listings before serving. The first one imports lerobot (torch, the
    commands' configs): seconds on a warm machine, more than a test waits for a Run on a fresh CI
    runner."""
    from lerobot_gui.adapters import options

    for command in [*options.CONFIG_COMMANDS, *options.ARGPARSE_COMMANDS]:
        # a listing that fails is for the tests to show, not for the start to stop on
        with contextlib.suppress(Exception):
            options.list_options(command)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=7899)
    args = parser.parse_args(argv)
    # nothing reaches the network: what is refused goes to the log the browser tests check at the end
    log = os.environ.get("LEROBOT_GUI_E2E_NETWORK_LOG")
    netguard.install(Path(log) if log else None)
    hub.fetch_models = hub_models
    fake_services()
    # the fake machine's serial ports, never this one's
    from lerobot_gui import devices

    devices.list_serial_ports = fake_serial_ports
    # a made-up computer's devices (torch isn't asked about this one's GPUs)
    torch_devices.available = lambda: ({"value": "cuda", "label": "cuda · Test GPU"}, {"value": "cpu", "label": "cpu"})
    base = Path(tempfile.mkdtemp(prefix="lerobot-gui-e2e-"))
    # no saved logins of this machine are looked at
    import huggingface_hub.constants

    huggingface_hub.constants.HF_TOKEN_PATH = str(base / "hf-home" / "token")
    # nor the Hub: a Hub policy's config (read for its defaults) is looked up in the made-up cache only
    huggingface_hub.constants.HF_HUB_OFFLINE = True
    os.environ["NETRC"] = str(base / "netrc")
    root, hf_home = make_workspace(base)
    # lerobot's and huggingface_hub's caches, made up in the fake workspace
    lerobot_cache = make_hub_cache(hf_home / "hub", [("dataset", "lerobot/pusht", 300_000)])
    hub_cache = make_hub_cache(base / "hf-home" / "hub", [("model", "lerobot/smolvla_base", 900_000)])
    huggingface_hub.constants.HF_HUB_CACHE = str(hub_cache)  # downloads would go here, not this machine's cache
    environment.lerobot_dirs = lambda: {
        "HF_LEROBOT_HOME": hf_home,
        "HF_LEROBOT_CALIBRATION": hf_home / "calibration",
        "HF_LEROBOT_HUB_CACHE": lerobot_cache,
    }
    environment.hub_dirs = lambda: {"HF_HOME": hub_cache.parent, "HF_HUB_CACHE": hub_cache}
    os.environ["HF_LEROBOT_HOME"] = str(hf_home)  # what the (fake) commands inherit
    s = Settings(
        config_dir=base / "config",  # presets: never this machine's
        root=root,
        hf_home=hf_home,
        calibration=calibration_folders(hf_home / "calibration"),
        bin_dir=make_bin_dir(base),
        fs_root=make_fs_root(base),
        port=args.port,
    )
    app = create_app(s, jobs=JobManager(s, arm_check=arms_ok))
    warm_up()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
