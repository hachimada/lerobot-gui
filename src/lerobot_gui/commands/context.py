"""Everything a page's fields and builder look at, with the lookups they share."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ..discovery import Snapshot
from ..paths import expand, shown
from .model import is_set


@dataclass(frozen=True)
class Accounts:
    """The Hugging Face login state, if it has been checked yet (it needs the network)."""

    loaded: bool = False
    hf: dict = field(default_factory=dict)


class CameraSchema(Protocol):
    """lerobot's camera types and their settings (adapters/cameras.py; a stand-in in unit tests)."""

    def types(self) -> Sequence[str]: ...

    def fields(self, cam_type: str) -> Sequence[dict]: ...

    def device_field(self, cam_type: str) -> str | None: ...


def basename(path: Any) -> str:
    parts = [p for p in str(path or "").split("/") if p]
    return parts[-1] if parts else ""


@dataclass
class Context:
    snap: Snapshot
    accounts: Accounts
    #: what the user changed on each page (page id -> field key -> value)
    stored: dict[str, dict]
    root: Path
    hf_home: Path
    page: str = ""
    #: the Hardware page's values, and the current page's (entered values, plus its GUI choices)
    hw: dict[str, Any] = field(default_factory=dict)
    v: dict[str, Any] = field(default_factory=dict)
    #: the installed lerobot's options for the current selection (flag -> option), once listed
    listing: dict[str, dict] | None = None
    #: what that listing was asked for (command, selections, policy path); None for a page without one
    options_query: tuple[str, dict[str, str], str | None] | None = None
    #: lerobot's camera types and settings
    cameras: CameraSchema | None = None

    def lerobot_option(self, flag: str) -> dict | None:
        return self.listing.get(flag) if self.listing is not None else None

    # -- people

    def hf_namespaces(self) -> list[str]:
        """Repo-id namespaces: the logged-in account and its organizations first, then local ones."""
        hf = self.accounts.hf
        return _unique([hf.get("user"), *(hf.get("orgs") or []), *self.snap.local.get("hf_namespaces", [])])

    def trackio_projects(self) -> list[str]:
        """The Trackio projects of the training runs here."""
        return list(self.snap.local.get("trackio_projects", []))

    def trackio_spaces(self) -> list[str]:
        """The Trackio Spaces of the training runs here."""
        return list(self.snap.local.get("trackio_spaces", []))

    # -- workspace

    def policy_info(self, path: Any) -> dict | None:
        """The local training run a checkpoint path belongs to (however the path is written)."""
        if not is_set(path):
            return None
        p = self._full(path)
        return next(
            (
                r
                for r in self.snap.policies
                if p in (self._full(r["last"]), *(self._full(s["path"]) for s in r["steps"]))
            ),
            None,
        )

    def _full(self, path: Any) -> str:
        return os.path.normpath(self.root / expand(str(path).strip()))

    def dataset_info(self, repo: Any) -> dict | None:
        return next((d for d in self.snap.datasets if d["repo_id"] == repo), None) if repo else None

    def dataset_dir(self, repo: str) -> str:
        """Where a dataset lives locally ($HF_LEROBOT_HOME/<repo_id>), relative to the workspace when it
        is inside it (commands run in the workspace)."""
        return shown(self.hf_home / repo, self.root)

    def calibrated(self, kind: str, cls: str, arm_id: Any) -> bool:
        return any(x["class"] == cls and x["id"] == arm_id for x in self.snap.calibrations.get(kind, []))

    # -- serial ports: the name lerobot-find-port reports, and the USB-serial board on it

    def port_entry(self, port: Any) -> dict | None:
        """The port a name refers to: its tty, or its board's by-id link."""
        p = str(port or "")
        return next((x for x in self.snap.ports if p and (p in x["aliases"] or p == x["board"])), None)

    def dev_of(self, port: Any) -> str:
        """The port as lerobot-find-port names it, behind any name of it or its board."""
        hit = self.port_entry(port)
        return hit["tty"] if hit else str(port or "")

    def board_of(self, port: Any) -> str | None:
        hit = self.port_entry(port)
        return hit["board"] if hit else None

    def tty_of_board(self, board: str) -> str | None:
        hit = next((x for x in self.snap.ports if x["board"] == board), None)
        return hit["tty"] if hit else None

    def board_label(self, board: str) -> str:
        """The serial number of a board that is plugged in, else its by-id name."""
        hit = next((x for x in self.snap.ports if x["board"] == board), None)
        return hit["serial"] if hit and hit["serial"] else basename(board)

    def port_connected(self, port: Any) -> bool:
        return self.port_entry(port) is not None

    def ttys(self) -> list[str]:
        return [x["tty"] for x in self.snap.ports]


def _unique(items: list) -> list[str]:
    return [x for x in dict.fromkeys(items) if isinstance(x, str) and x]
