"""The environment the commands run in. They inherit the GUI's, so this is theirs too.

- lerobot's data dirs as lerobot and huggingface_hub resolve them (read from their constants, not
  computed here), and whether the environment sets them;
- the environment variables of the libraries the commands use that are set (by prefix), and a few
  listed whether set or not;
- the Python environment and the lerobot that run.

The value of a secret (a name with TOKEN, KEY, SECRET, ...) is never returned: only that it is set.
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
from collections.abc import Mapping
from pathlib import Path

from ..paths import tilde
from ..settings import Settings

#: set variables with these prefixes are listed
PREFIXES = ("HF_", "HUGGING_FACE_", "LEROBOT_", "TRACKIO_", "CUDA_")
#: listed whether set or not: the display the commands get, and the credentials the GUI itself checks
ALWAYS = ("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "HF_TOKEN", "LEROBOT_GUI_TOKEN")
_SECRET_WORDS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "CREDENTIAL")


def is_secret(name: str) -> bool:
    return any(word in name.upper() for word in _SECRET_WORDS)


def lerobot_dirs() -> dict[str, Path]:
    from lerobot.utils import constants

    return {
        n: Path(getattr(constants, n)) for n in ("HF_LEROBOT_HOME", "HF_LEROBOT_CALIBRATION", "HF_LEROBOT_HUB_CACHE")
    }


def hub_dirs() -> dict[str, Path]:
    from huggingface_hub import constants

    return {n: Path(getattr(constants, n)) for n in ("HF_HOME", "HF_HUB_CACHE")}


def locations(env: Mapping[str, str] = os.environ) -> list[dict]:
    """{name, value, read_from, from_env} for each dir, or {name, error} when it can't be read. `env`:
    the commands' environment."""
    out: list[dict] = []
    for module, read in (("lerobot.utils.constants", lerobot_dirs), ("huggingface_hub.constants", hub_dirs)):
        try:
            found = read()
        except Exception as exc:  # e.g. lerobot refuses to start with a variable it no longer reads
            out.append({"name": module, "error": f"{type(exc).__name__}: {exc}".splitlines()[0][:300]})
            continue
        for name, path in found.items():
            out.append({"name": name, "value": tilde(path), "read_from": module, "from_env": name in env})
    return out


def _login_note(name: str, is_set: bool) -> str | None:
    """For a service's credential variable: which login the commands use (the variable comes before
    the login saved by `hf auth login`). Only paths, never a token."""
    from . import accounts

    saved = {"HF_TOKEN": accounts.hf_saved_login}.get(name)
    if saved is None:
        return None
    if is_set:
        return "This is the login used: it comes before a saved one."
    where = saved()
    return f"The login saved in `{where}` is used." if where else "No login is saved either."


def variables(env: Mapping[str, str] = os.environ) -> list[dict]:
    """{name, set, value, secret, note}: the set variables with PREFIXES, and ALWAYS, sorted by name.
    `env`: the commands' environment (the GUI's as it was started)."""
    names = {n for n in env if n.startswith(PREFIXES)} | set(ALWAYS)
    out = []
    for name in sorted(names):
        value = env.get(name)
        secret = is_secret(name)
        out.append(
            {
                "name": name,
                "set": value is not None,
                "secret": secret,
                "value": None if secret or value is None else tilde(value),
                "note": _login_note(name, value is not None),
            }
        )
    return out


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def runtime(s: Settings) -> list[dict]:
    """What runs: the workspace, the commands' Python environment and the versions."""
    return [
        {"name": "Workspace", "value": tilde(s.root)},
        {"name": "Commands", "value": tilde(s.bin_dir)},
        {"name": "Python", "value": platform.python_version()},
        {"name": "lerobot", "value": _version("lerobot")},
        {"name": "lerobot-gui", "value": _version("lerobot-gui")},
    ]
