"""Presets of the command pages (Calibrate, Teleoperate, Record, Train, Rollout)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import commands, presets, schemas
from .deps import CtxDep

router = APIRouter()


class SaveRequest(BaseModel):
    values: dict


def _page(page_id: str) -> str:
    try:
        page = commands.get_page(page_id)
    except ValueError:
        page = None
    if page is None or not page.presets:
        raise HTTPException(404, "No presets for this page")
    return page.id


@router.get("/presets/{page}", response_model=list[schemas.PresetInfo])
def list_presets(ctx: CtxDep, page: str) -> list[dict]:
    return presets.listing(ctx.settings, _page(page))


@router.get("/presets/{page}/{name}", response_model=schemas.Preset)
def load_preset(ctx: CtxDep, page: str, name: str) -> dict:
    try:
        return presets.load(ctx.settings, _page(page), name)
    except presets.PresetError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/presets/{page}/{name}", response_model=schemas.Preset)
def save_preset(ctx: CtxDep, page: str, name: str, req: SaveRequest) -> dict:
    try:
        return presets.save(ctx.settings, _page(page), name, req.values)
    except presets.PresetError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/presets/{page}/{name}", response_model=list[schemas.PresetInfo])
def delete_preset(ctx: CtxDep, page: str, name: str) -> list[dict]:
    try:
        presets.delete(ctx.settings, _page(page), name)
    except presets.PresetError as exc:
        raise HTTPException(404, str(exc)) from exc
    return presets.listing(ctx.settings, _page(page))
