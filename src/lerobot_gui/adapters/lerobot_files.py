"""What lerobot writes, read the way lerobot writes it: its datasets, its training runs and its calibration files.

The datasets are `<HF_LEROBOT_HOME>/<namespace>/<name>/meta/info.json` (and `meta/tasks.parquet`), a training
run is a lerobot-train output dir (`checkpoints/<step>/pretrained_model/config.json`, `train_config.json`), a
calibration file is `<folder>/<class>/<id>.json`. tests/contract checks them against files lerobot's own code
writes.
"""

from __future__ import annotations

import functools
import json
import os
from collections.abc import Iterable
from pathlib import Path

from ..settings import Settings


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def dataset_tasks(root: Path) -> list[str]:
    path = root / "meta" / "tasks.parquet"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []
    return list(_read_tasks(str(path), mtime))


@functools.lru_cache(maxsize=256)
def _read_tasks(path: str, _mtime: float) -> tuple[str, ...]:
    try:
        import pandas as pd

        df = pd.read_parquet(path)
        tasks = df["task"].tolist() if "task" in df.columns else df.index.tolist()
    except Exception:
        return ()
    return tuple(str(t) for t in tasks)


def datasets(s: Settings) -> list[dict]:
    """Local lerobot datasets (<HF_LEROBOT_HOME>/<namespace>/<name>/meta/info.json), newest first."""
    out = []
    for info_path in sorted(s.hf_home.glob("*/*/meta/info.json")):
        root = info_path.parent.parent
        info = read_json(info_path)
        if not info:
            continue
        features = info.get("features", {})
        out.append(
            {
                "repo_id": f"{root.parent.name}/{root.name}",
                "path": s.rel(root),
                "fps": info.get("fps"),
                "episodes": info.get("total_episodes"),
                "frames": info.get("total_frames"),
                "robot_type": info.get("robot_type"),
                "cameras": [k.split(".", 2)[2] for k in features if k.startswith("observation.images.")],
                "tasks": dataset_tasks(root),
                "mtime": info_path.stat().st_mtime,
            }
        )
    out.sort(key=lambda d: d["mtime"], reverse=True)
    return out


#: how many folders deep below the workspace a training run is looked for
RUN_DEPTH = 5


def _is_run(d: Path) -> bool:
    """A lerobot-train output dir: `checkpoints/<step>/pretrained_model/config.json`."""
    try:
        return any((c / "pretrained_model" / "config.json").is_file() for c in (d / "checkpoints").iterdir())
    except OSError:
        return False


def _run_dirs(s: Settings, extra: Iterable[Path] = ()) -> set[Path]:
    """Training runs in the workspace (found by their shape, not by a folder name) and in `extra`."""
    found: set[Path] = set()
    seen: set[str] = set()

    def walk(d: str, depth: int) -> None:
        real = os.path.realpath(d)
        if real in seen:  # a symlink loop, or a folder linked twice
            return
        seen.add(real)
        try:
            with os.scandir(d) as it:
                entries = list(it)
        except OSError:
            return
        names = {e.name for e in entries}
        if "checkpoints" in names and _is_run(Path(d)):
            found.add(Path(real))
            return
        # not inside Python environments or lerobot datasets: no training run there
        if depth >= RUN_DEPTH or "pyvenv.cfg" in names or Path(d, "meta", "info.json").is_file():
            return
        for e in entries:
            if not e.name.startswith(".") and e.name != "node_modules" and _is_dir(e):
                walk(e.path, depth + 1)

    walk(str(s.root), 0)
    for d in extra:
        path = d if d.is_absolute() else s.root / d
        if _is_run(path):
            found.add(path.resolve())
    return found


def _is_dir(entry: os.DirEntry) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        return False


def policies(s: Settings, extra: Iterable[Path] = ()) -> list[dict]:
    """Training runs with checkpoints (lerobot-train output dirs), newest first. `extra`: output dirs
    of runs the GUI started, which may lie outside the workspace."""
    runs = []
    for run_dir in _run_dirs(s, extra):
        ckpt_dir = run_dir / "checkpoints"
        steps = [
            {"step": d.name, "path": s.rel(d / "pretrained_model")}
            for d in ckpt_dir.iterdir()
            if d.name != "last" and (d / "pretrained_model" / "config.json").exists()
        ]
        if not steps:
            continue
        steps.sort(key=lambda x: int(x["step"]) if x["step"].isdigit() else -1, reverse=True)
        last = ckpt_dir / "last"
        latest = (last if last.exists() else ckpt_dir / steps[0]["step"]) / "pretrained_model"
        cfg = read_json(latest / "config.json")
        train = read_json(latest / "train_config.json")
        ptype = cfg.get("type")
        tracking: dict = t if isinstance(t := train.get("trackio"), dict) else {}
        logged = tracking.get("enable") is True  # (the project has a default: it is there for every run)
        policy: dict = t if isinstance(t := train.get("policy"), dict) else {}
        runs.append(
            {
                "name": run_dir.name,
                "dir": s.rel(run_dir),
                "type": ptype,
                "steps": steps,
                "last": s.rel(last / "pretrained_model") if last.exists() else steps[0]["path"],
                "last_step": os.path.basename(os.path.realpath(last)) if last.exists() else steps[0]["step"],
                "train_config": s.rel(latest / "train_config.json") if train else None,
                "cameras": [
                    k.split(".", 2)[2]
                    for k, v in cfg.get("input_features", {}).items()
                    if k.startswith("observation.images.") and v.get("type") == "VISUAL"
                ],
                "chunk_size": cfg.get("chunk_size"),
                "horizon": cfg.get("horizon"),
                "n_action_steps": cfg.get("n_action_steps"),
                "dataset": (train.get("dataset") or {}).get("repo_id"),
                # the observation names the run renamed for the policy (`--rename_map`)
                "rename_map": rename if isinstance(rename := train.get("rename_map"), dict) and rename else None,
                "steps_total": train.get("steps"),
                # where it pushed and logged to (--policy.repo_id, Trackio's project and Space)
                "repo_id": policy.get("repo_id"),
                "trackio_project": tracking.get("project") if logged else None,
                "trackio_space": tracking.get("space_id") if logged else None,
                "mtime": latest.stat().st_mtime,
            }
        )
    runs.sort(key=lambda r: r["mtime"], reverse=True)
    return runs


def calibrations(folders: dict[str, Path]) -> dict[str, list[dict]]:
    """lerobot's calibration files in its folders of robots and teleoperators (`Settings.calibration`):
    <folder>/<class>/<id>.json."""
    return {
        kind: [{"class": p.parent.name, "id": p.stem} for p in sorted(folder.glob("*/*.json"))]
        for kind, folder in folders.items()
    }
