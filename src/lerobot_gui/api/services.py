"""The Services page: Hugging Face (local data, the account's repos)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import schemas
from ..adapters.commands import LEROBOT_COMMANDS
from .deps import CtxDep

router = APIRouter()


class DeleteRequest(BaseModel):
    kind: str
    repo_id: str | None = None
    repo_type: str | None = None
    cache: str | None = None
    calibration_kind: str | None = None
    # pydantic: `class` is a keyword
    cls: str | None = None
    id: str | None = None


@router.get("/hf/local", response_model=schemas.HfLocal)
def hf_local(ctx: CtxDep) -> dict:
    from ..adapters import hf_local as local

    return local.listing(ctx.settings)


@router.post("/hf/local/delete", response_model=schemas.HfLocal)
def hf_local_delete(ctx: CtxDep, req: DeleteRequest) -> dict:
    from ..adapters import hf_local as local

    # the data is lerobot's: the Trackio dashboard may stay open
    running = next((j for j in ctx.jobs.list() if j.running and j.command in LEROBOT_COMMANDS), None)
    if running:
        raise HTTPException(409, f"{running.command} is running: stop it before deleting data it may use.")
    item = {**req.model_dump(exclude={"cls"}), "class": req.cls}
    try:
        message = local.delete(ctx.settings, item)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    ctx.discovery.snapshot(refresh=True)  # the datasets the pages offer
    return {"message": message, **local.listing(ctx.settings)}


@router.get("/hf/cloud", response_model=schemas.HfCloud)
def hf_cloud(refresh: bool = False) -> dict:
    from ..adapters import accounts, hub

    status = accounts.peek("hf") or accounts.hf_status()
    if not status.get("logged_in"):
        return {"owners": [], "logged_in": False}
    return {**hub.cloud(status.get("user"), status.get("orgs") or [], refresh), "logged_in": True}
