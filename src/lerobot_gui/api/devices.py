"""What is plugged in and what is in the workspace: ports, cameras, datasets, checkpoints, frames."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import devices, schemas, workspace
from ..adapters import lerobot_files
from .deps import CtxDep

router = APIRouter()


@router.get("/ports", response_model=schemas.Ports)
def ports(ctx: CtxDep) -> dict:
    s = ctx.settings
    return {
        "ports": devices.ports(s.fs_root),
        "calibrations": lerobot_files.calibrations(s.calibration),
    }


@router.get("/discover", response_model=schemas.Discover)
def discover(ctx: CtxDep) -> dict:
    """Rescan: the ports (as /ports), and how many datasets and training runs a fresh scan found."""
    snap = ctx.discovery.snapshot(refresh=True)
    return {
        "ports": snap.ports,
        "calibrations": snap.calibrations,
        "datasets": len(snap.datasets),
        "policies": len(snap.policies),
        "local": snap.local,
    }


@router.get("/captured-images", response_model=list[schemas.CapturedImage])
def captured_images(ctx: CtxDep, dir: str = "", record_time: float | None = None) -> list[dict]:
    """The frames in `dir`, each marked `older` when an earlier run left it. `record_time`: Find
    cameras' --record-time-s as entered."""
    try:
        images = workspace.captured_images(ctx.settings, dir)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    runs = [j for j in ctx.jobs.list() if j.command == "lerobot-find-cameras"]
    since = max(j.started for j in runs) - 1 if runs else None
    duration = record_time if record_time and record_time > 0 else workspace.default_record_time()
    return workspace.mark_older(images, since, duration + 2 if duration else None)


@router.delete("/captured-images/{name}", response_model=schemas.Ok)
def delete_captured_image(ctx: CtxDep, name: str, dir: str = "") -> dict:
    """Delete one frame (one an earlier run left, which can stay for a long time)."""
    if any(j.running and j.command == "lerobot-find-cameras" for j in ctx.jobs.list()):
        raise HTTPException(409, "Find cameras is running: wait for it to finish.")
    try:
        path = workspace.captured_image_path(ctx.settings, name, dir)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(404, "No such image")
    path.unlink()
    return {"ok": True}


@router.get("/captured-images/{name}")
def captured_image(ctx: CtxDep, name: str, dir: str = "") -> FileResponse:
    try:
        path = workspace.captured_image_path(ctx.settings, name, dir)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(404, "No such image")
    return FileResponse(path, headers={"Cache-Control": "no-store"})
