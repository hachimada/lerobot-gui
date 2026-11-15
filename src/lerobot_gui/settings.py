"""Runtime settings: where the workspace, lerobot data and lerobot commands are."""

from __future__ import annotations

import dataclasses
import os
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: the port the GUI listens on unless told otherwise
DEFAULT_PORT = 7878


def default_config_dir() -> Path:
    """The GUI's own settings dir (presets): $XDG_CONFIG_HOME/lerobot-gui, else ~/.config/lerobot-gui."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "lerobot-gui"


def default_hf_home() -> Path:
    """lerobot's data dir, as lerobot itself resolves it (HF_LEROBOT_HOME, else $HF_HOME/lerobot)."""
    from lerobot.utils.constants import HF_LEROBOT_HOME

    return Path(HF_LEROBOT_HOME)


def default_calibration() -> dict[str, Path]:
    """lerobot's calibration folders of robots and teleoperators, as lerobot resolves them:
    HF_LEROBOT_CALIBRATION (else <HF_LEROBOT_HOME>/calibration) / ROBOTS or TELEOPERATORS."""
    from lerobot.utils.constants import HF_LEROBOT_CALIBRATION, ROBOTS, TELEOPERATORS

    base = Path(HF_LEROBOT_CALIBRATION)
    return {"robots": base / ROBOTS, "teleoperators": base / TELEOPERATORS}


@dataclass(frozen=True)
class Settings:
    #: the lerobot workspace: commands run here, `outputs/` lives here
    root: Path
    #: lerobot's data dir (datasets, calibration files); the commands resolve it the same way
    hf_home: Path
    #: lerobot's calibration folders, {"robots": ..., "teleoperators": ...}: <folder>/<class>/<id>.json
    calibration: dict[str, Path] = field(hash=False)
    #: where the `lerobot-*` commands are (the Python environment the GUI runs in)
    bin_dir: Path
    port: int = DEFAULT_PORT
    host: str = "127.0.0.1"
    #: filesystem root for device discovery (/dev, /sys); tests point it at a fake tree
    fs_root: Path = Path("/")
    #: the GUI's own settings (presets), outside the workspace
    config_dir: Path = field(default_factory=lambda: default_config_dir())
    #: per-launch API token embedded in the page
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    #: the environment the GUI was started with, which the commands get. Not the GUI's os.environ as
    #: it is later: libraries the GUI uses may add to it while it runs, and a command must not inherit
    #: what they set for the GUI's own process.
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ), repr=False, compare=False, hash=False)

    @classmethod
    def from_env(cls, root: str | Path | None = None, port: int = DEFAULT_PORT) -> Settings:
        s = cls(
            root=Path(root or os.environ.get("LEROBOT_GUI_ROOT") or os.getcwd()).resolve(),
            hf_home=default_hf_home(),
            calibration=default_calibration(),
            bin_dir=Path(sys.executable).parent,
            port=port,
        )
        # a fixed token lets `npm run dev` (frontend/vite.config.ts) talk to this server
        token = os.environ.get("LEROBOT_GUI_TOKEN")
        return dataclasses.replace(s, token=token) if token else s

    @property
    def allowed_hosts(self) -> set[str]:
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def rel(self, path: Path) -> str:
        """`path` as the GUI shows and offers it (paths.shown)."""
        from .paths import shown

        return shown(path, self.root)
