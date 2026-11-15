"""Fixtures: a fake machine (/dev, /sys), a fake workspace and fake lerobot commands (see fakes.py).

The tests outside tests/contract don't use lerobot. With LEROBOT_GUI_TESTS_WITHOUT_LEROBOT=1 an
import of lerobot fails, which CI uses to keep it that way (the contract tests are then skipped).
No test reaches the network (netguard.py): one that tries fails.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from lerobot_gui.settings import Settings

from . import netguard
from .fakes import (  # noqa: F401  re-exported for the tests
    BY_ID,
    FAKE_COMMANDS,
    FIND_CAMERAS_OPTIONS,
    FOLLOWER_CAL,
    FOLLOWER_SERIAL,
    LEADER_CAL,
    LEADER_SERIAL,
    MOTORS,
    calibration_folders,
    fake_serial_ports,
    make_bin_dir,
    make_fs_root,
    make_workspace,
)


class _NoLerobot:
    def find_spec(self, name, path=None, target=None):
        if name == "lerobot" or name.startswith("lerobot."):
            raise ImportError(f"{name}: lerobot is blocked (LEROBOT_GUI_TESTS_WITHOUT_LEROBOT)")
        return None


if os.environ.get("LEROBOT_GUI_TESTS_WITHOUT_LEROBOT"):
    sys.meta_path.insert(0, _NoLerobot())

netguard.install()


@pytest.fixture(autouse=True)
def _no_network():
    """A test that reached beyond this computer fails, even when the code swallowed the refusal."""
    before = len(netguard.attempts)
    yield
    if reached := netguard.attempts[before:]:
        pytest.fail(f"The test reached for the network: {', '.join(reached)}", pytrace=False)


@pytest.fixture
def fs_root(tmp_path: Path) -> Path:
    return make_fs_root(tmp_path)


@pytest.fixture
def workspace(tmp_path: Path) -> tuple[Path, Path]:
    return make_workspace(tmp_path)


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    return make_bin_dir(tmp_path)


@pytest.fixture
def settings(workspace, fs_root, bin_dir, monkeypatch) -> Settings:
    root, hf_home = workspace
    # the commands inherit the environment, as lerobot reads its data dir from it
    monkeypatch.setenv("HF_LEROBOT_HOME", str(hf_home))
    return Settings(
        root=root, hf_home=hf_home, calibration=calibration_folders(hf_home / "calibration"), bin_dir=bin_dir,
        fs_root=fs_root, port=7878, token="test-token", config_dir=root.parent / "config",
    )  # fmt: skip


@pytest.fixture
def client(settings, tmp_path):
    from fastapi.testclient import TestClient

    from lerobot_gui.app import TOKEN_PLACEHOLDER, create_app

    # a page of its own: the tests don't depend on whether this checkout's frontend is built
    web = tmp_path / "web-build"
    web.mkdir()
    (web / "index.html").write_text(f'<meta name="lerobot-gui-token" content="{TOKEN_PLACEHOLDER}">')
    app = create_app(settings, web_dir=web)
    with TestClient(app, base_url="http://127.0.0.1:7878", headers={"X-Token": settings.token}) as c:
        yield c


@pytest.fixture(autouse=True)
def _no_root_from_the_environment():
    os.environ.pop("LEROBOT_GUI_ROOT", None)


@pytest.fixture(autouse=True)
def _without_lerobot(request, monkeypatch, tmp_path):
    """Outside the lerobot contract tests, what is read from lerobot comes from fakes."""
    if request.node.get_closest_marker("lerobot") is not None:
        return
    from lerobot_gui import app, settings
    from lerobot_gui.adapters import cameras, environment, options, torch_devices
    from lerobot_gui.api.deps import Listings

    from .commands_helpers import FakeCameras

    # the option listing Run uses, lerobot-find-cameras' arguments, the camera types, lerobot's data dir
    monkeypatch.setattr(app, "lerobot_listings", lambda: Listings(cached=options.cached_options, full=lambda *_: None))
    listings = options._listings()
    listings.get("lerobot-find-cameras", lambda: (FIND_CAMERAS_OPTIONS, True))
    monkeypatch.setattr(options, "_LISTINGS", listings)
    monkeypatch.setattr(cameras, "LEROBOT", FakeCameras())
    home = Path("/nonexistent/lerobot-home")
    monkeypatch.setattr(settings, "default_hf_home", lambda: home)
    monkeypatch.setattr(settings, "default_calibration", lambda: calibration_folders(home / "calibration"))
    monkeypatch.setattr(
        environment,
        "lerobot_dirs",
        lambda: {
            "HF_LEROBOT_HOME": home,
            "HF_LEROBOT_CALIBRATION": home / "calibration",
            "HF_LEROBOT_HUB_CACHE": home / "hub",
        },
    )
    # the devices of a made-up computer with one GPU
    monkeypatch.setattr(
        torch_devices,
        "available",
        lambda: ({"value": "cuda", "label": "cuda · Test GPU"}, {"value": "cpu", "label": "cpu"}),
    )
    # never this computer's GUI settings (presets)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    # never this computer's saved logins
    import huggingface_hub.constants

    monkeypatch.setattr(huggingface_hub.constants, "HF_TOKEN_PATH", str(tmp_path / "hf-home" / "token"))
    monkeypatch.setenv("NETRC", str(tmp_path / "netrc"))
    # never this computer's Hugging Face cache
    hub = tmp_path / "hf-home"
    monkeypatch.setattr(environment, "hub_dirs", lambda: {"HF_HOME": hub, "HF_HUB_CACHE": hub / "hub"})


@pytest.fixture(autouse=True)
def _no_real_serial_ports(monkeypatch):
    """Every test, the lerobot contract tests too: the serial ports of the fake machine, never this one's."""
    from lerobot_gui import devices

    monkeypatch.setattr(devices, "list_serial_ports", fake_serial_ports)
