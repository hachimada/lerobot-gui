"""One snapshot of the machine and the workspace, as the command builders see it.

Ports, cameras and calibration files are read live (a few directory listings). Datasets, training
runs and the names found in them are scanned at most every `ttl` seconds, since the form is rebuilt
on every keystroke.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from . import devices, workspace
from .adapters import lerobot_files
from .cache import Cache
from .settings import Settings


@dataclass(frozen=True)
class Snapshot:
    ports: list[dict] = field(default_factory=list)
    calibrations: dict[str, list[dict]] = field(default_factory=lambda: {"robots": [], "teleoperators": []})
    datasets: list[dict] = field(default_factory=list)
    policies: list[dict] = field(default_factory=list)
    #: dataset / model namespaces and Trackio projects and Spaces found on disk
    local: dict[str, list[str]] = field(
        default_factory=lambda: {"hf_namespaces": [], "trackio_projects": [], "trackio_spaces": []}
    )


class Discovery:
    def __init__(self, s: Settings, ttl: float = 5.0, run_dirs: Callable[[], Iterable[Path]] = tuple):
        self.settings = s
        #: output dirs of the training runs the GUI started (they may lie outside the workspace)
        self.run_dirs = run_dirs
        #: the workspace scan (datasets, training runs, the names found in them), kept for `ttl`
        self._scans: Cache[str, dict] = Cache(ttl)

    def snapshot(self, refresh: bool = False) -> Snapshot:
        s = self.settings

        def scan() -> dict:
            found = lerobot_files.datasets(s)
            runs = lerobot_files.policies(s, self.run_dirs())
            return {"datasets": found, "policies": runs, "local": workspace.local_names(found, runs)}

        ws = self._scans.get("workspace", scan, refresh=refresh)
        return Snapshot(
            ports=devices.ports(s.fs_root),
            calibrations=lerobot_files.calibrations(s.calibration),
            **ws,
        )
