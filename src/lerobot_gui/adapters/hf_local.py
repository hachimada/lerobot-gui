"""What lerobot and huggingface_hub keep on this computer, and deleting it.

- lerobot's datasets in HF_LEROBOT_HOME (as the GUI finds them elsewhere), with their size on disk
- the calibration files, in lerobot's calibration folders (`Settings.calibration`)
- lerobot's Hub cache (datasets read from the Hub) and huggingface_hub's cache (models and datasets
  downloaded), read with huggingface_hub's public `scan_cache_dir`; their dirs are read from
  lerobot and huggingface_hub (see adapters/environment.py)

Deleting takes what the listing shows: a dataset by repo id, a calibration file by kind, class and
id, a cached repo by cache, type and id. Anything else is refused.
"""

from __future__ import annotations

import contextlib
import os
import shutil
from pathlib import Path

from ..paths import tilde
from ..settings import Settings
from . import environment, lerobot_files


def size_on_disk(path: Path) -> int:
    """Bytes of the files under `path` (symlinks not followed)."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            with contextlib.suppress(OSError):  # gone meanwhile
                total += os.lstat(os.path.join(root, name)).st_size
    return total


def _cache_dirs() -> dict[str, Path | str]:
    """Each cache's dir, or the error reading it."""
    out: dict[str, Path | str] = {}
    for name, read in (("HF_LEROBOT_HUB_CACHE", environment.lerobot_dirs), ("HF_HUB_CACHE", environment.hub_dirs)):
        try:
            out[name] = read()[name]
        except Exception as exc:
            out[name] = f"{type(exc).__name__}: {exc}".splitlines()[0][:300]
    return out


def _scan(path: Path):
    from huggingface_hub import scan_cache_dir
    from huggingface_hub.errors import CacheNotFound

    try:
        return scan_cache_dir(path)
    except CacheNotFound:
        return None


def _when(ts: float | None) -> float | None:
    return float(ts) if ts else None


def caches() -> list[dict]:
    out = []
    for name, path in _cache_dirs().items():
        if isinstance(path, str):
            out.append({"name": name, "path": None, "size": 0, "repos": [], "error": path})
            continue
        info = _scan(path)
        repos = sorted(info.repos, key=lambda r: r.last_accessed or 0, reverse=True) if info else []
        out.append(
            {
                "name": name,
                "path": tilde(path),
                "size": info.size_on_disk if info else 0,
                "repos": [
                    {
                        "repo_id": r.repo_id,
                        "repo_type": r.repo_type,
                        "size": r.size_on_disk,
                        "files": r.nb_files,
                        "revisions": len(r.revisions),
                        "last_accessed": _when(r.last_accessed),
                        "last_modified": _when(r.last_modified),
                    }
                    for r in repos
                ],
                # what scan_cache_dir couldn't read (a broken entry), as it says
                "error": ("; ".join(str(w) for w in info.warnings)[:300] or None) if info else None,
            }
        )
    return out


def calibration_files(s: Settings) -> list[dict]:
    found = lerobot_files.calibrations(s.calibration)
    return [
        {
            "kind": kind,
            "class": c["class"],
            "id": c["id"],
            "path": s.rel(_calibration_path(s, kind, c["class"], c["id"])),
        }
        for kind in ("robots", "teleoperators")
        for c in found.get(kind, [])
    ]


def _calibration_path(s: Settings, kind: str, cls: str, arm_id: str) -> Path:
    return s.calibration[kind] / cls / f"{arm_id}.json"


def listing(s: Settings) -> dict:
    datasets = [{**d, "size": size_on_disk(s.hf_home / d["repo_id"])} for d in lerobot_files.datasets(s)]
    return {
        "home": s.rel(s.hf_home),
        "datasets": datasets,
        "calibrations": calibration_files(s),
        "caches": caches(),
    }


def delete(s: Settings, item: dict) -> str:
    """Delete one listed item; what was deleted, as a message. ValueError when it isn't listed."""
    kind = item.get("kind")
    if kind == "dataset":
        repo = str(item.get("repo_id") or "")
        if repo not in {d["repo_id"] for d in lerobot_files.datasets(s)}:
            raise ValueError(f"No local dataset `{repo}`.")
        path = (s.hf_home / repo).resolve()
        if not path.is_relative_to(s.hf_home.resolve()) or path == s.hf_home.resolve():
            raise ValueError(f"No local dataset `{repo}`.")
        shutil.rmtree(path)
        return f"Deleted the dataset `{repo}` ({tilde(path)})."
    if kind == "calibration":
        key = (item.get("calibration_kind"), item.get("class"), item.get("id"))
        listed = {(c["kind"], c["class"], c["id"]) for c in calibration_files(s)}
        if key not in listed:
            raise ValueError("No such calibration file.")
        path = _calibration_path(s, *key)  # type: ignore[arg-type]
        path.unlink()
        return f"Deleted the calibration file `{s.rel(path)}`."
    if kind == "cache":
        name = item.get("cache")
        dirs = _cache_dirs()
        path = dirs.get(str(name))
        if not isinstance(path, Path):
            raise ValueError(f"No cache `{name}`.")
        info = _scan(path)
        repo = next(
            (
                r
                for r in (info.repos if info else [])
                if r.repo_id == item.get("repo_id") and r.repo_type == item.get("repo_type")
            ),
            None,
        )
        if repo is None or info is None:
            raise ValueError(f"No `{item.get('repo_id')}` in {name}.")
        info.delete_revisions(*(rev.commit_hash for rev in repo.revisions)).execute()
        if repo.repo_path.exists():  # deleting every revision may leave the repo's folder behind
            shutil.rmtree(repo.repo_path)
        return f"Deleted `{repo.repo_id}` ({repo.repo_type}) from {name}."
    raise ValueError(f"Unknown item kind `{kind}`.")
