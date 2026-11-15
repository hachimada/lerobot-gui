"""The environment the commands run in (they inherit the GUI's)."""

from __future__ import annotations

from fastapi import APIRouter

from .. import schemas
from .deps import CtxDep

router = APIRouter()


@router.get("/environment", response_model=schemas.EnvironmentInfo)
def environment(ctx: CtxDep) -> dict:
    from ..adapters import environment as env

    # the environment the commands get
    s = ctx.settings
    return {"locations": env.locations(s.env), "variables": env.variables(s.env), "runtime": env.runtime(s)}
