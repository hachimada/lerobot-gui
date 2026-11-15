"""The workspace as the GUI sees it: the names found in its datasets and runs, and Find cameras' frames.

lerobot's own files (datasets, training runs, calibration files) are read by adapters/lerobot_files.py.
"""

from __future__ import annotations

from pathlib import Path

from .adapters.commands import CAPTURE_SUFFIXES, captured_image_device
from .devices import natural_key
from .paths import expand
from .settings import Settings


def local_names(datasets: list[dict], runs: list[dict]) -> dict[str, list[str]]:
    """Names found on disk, offered in the fields: the namespaces of the local datasets and of the models
    trained here, and the Trackio projects and Spaces of the runs logged to Trackio."""
    hf: list[str] = []
    projects: list[str] = []
    spaces: list[str] = []

    def add(names: list[str], value: object) -> None:
        if isinstance(value, str) and value and value not in names:
            names.append(value)

    for d in datasets:
        add(hf, d["repo_id"].split("/", 1)[0])
    for run in runs:
        add(projects, run.get("trackio_project"))
        add(spaces, run.get("trackio_space"))
        repo = run.get("repo_id")
        if isinstance(repo, str) and "/" in repo:
            add(hf, repo.split("/", 1)[0])
    return {"hf_namespaces": hf, "trackio_projects": projects, "trackio_spaces": spaces}


def default_capture_dir() -> str:
    """lerobot-find-cameras' own default --output-dir."""
    from .adapters.options import list_options

    found = next(o for o in list_options("lerobot-find-cameras")["options"] if o["flag"] == "output-dir")
    return found["default"]


def default_record_time() -> float | None:
    """lerobot-find-cameras' own default --record-time-s."""
    from .adapters.options import list_options

    found = next((o for o in list_options("lerobot-find-cameras")["options"] if o["flag"] == "record-time-s"), None)
    try:
        return float(found["default"]) if found and found.get("default") is not None else None
    except ValueError:
        return None


def mark_older(images: list[dict], since: float | None, window: float | None) -> list[dict]:
    """Each frame with `older`: left by an earlier run, not the last capture's (all are kept).

    `since`: when the last Find cameras run of this GUI started: the frames it didn't write. Else the
    frames written more than `window` seconds before the newest one (a run keeps writing each
    camera's frame until it ends, so its own frames are that close together).
    """
    newest = max((i["mtime"] for i in images), default=0.0)
    for i in images:
        if since is not None:
            i["older"] = i["mtime"] < since
        else:
            i["older"] = window is not None and i["mtime"] < newest - window
    return images


def capture_dir(s: Settings, rel: str) -> Path:
    """lerobot-find-cameras' --output-dir, which must be inside the workspace."""
    target = (s.root / expand(rel or default_capture_dir())).resolve()
    if not target.is_relative_to(s.root.resolve()):
        raise ValueError("The image dir must be inside the workspace")
    return target


def captured_images(s: Settings, rel: str = "") -> list[dict]:
    base = capture_dir(s, rel)
    out = []
    for p in sorted(base.iterdir(), key=lambda x: natural_key(x.name)) if base.is_dir() else []:
        if p.suffix.lower() not in CAPTURE_SUFFIXES or not p.is_file():
            continue
        cam_type, device = captured_image_device(p.stem)
        width, height = _image_size(p)
        out.append(
            {
                "name": p.name,
                "type": cam_type,
                "device": device,
                "mtime": p.stat().st_mtime,
                # the frame lerobot captured: offered as the camera's width and height
                "width": width,
                "height": height,
            }
        )
    return out


def _image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(path) as img:  # reads the header only
            return img.size
    except Exception:
        return None, None


def captured_image_path(s: Settings, name: str, rel: str = "") -> Path:
    path = capture_dir(s, rel) / name
    if "/" in name or "\\" in name or name.startswith(".") or path.suffix.lower() not in CAPTURE_SUFFIXES:
        raise ValueError("Invalid image name")
    return path
