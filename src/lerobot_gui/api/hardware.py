"""The Hardware page: its fields and view for the values stored in the browser, and Check arms."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .. import commands, schemas
from ..commands import hardware
from ..commands.context import Accounts, Context
from .deps import CtxDep

router = APIRouter()


class HardwareRequest(BaseModel):
    #: the Hardware page's values, as stored
    hardware: dict = {}
    #: the last Check arms result
    arm_check: schemas.ArmCheck | None = None


class ArmsRequest(BaseModel):
    #: the Hardware page's values, as stored
    hardware: dict = {}


def _context(ctx: CtxDep, values: dict) -> Context:
    s = ctx.settings
    snap = ctx.discovery.snapshot()
    return commands.make_context(snap, Accounts(), {"hardware": values}, root=s.root, hf_home=s.hf_home)


@router.post("/hardware", response_model=schemas.HardwareForm)
def hardware_form(ctx: CtxDep, req: HardwareRequest) -> schemas.HardwareForm:
    """Each arm's port and id fields, what is plugged in, the setup status and the Check arms result explained."""
    return hardware.form(_context(ctx, req.hardware), req.arm_check)


@router.post("/check-arms", response_model=schemas.ArmCheck)
def check_arms(ctx: CtxDep, req: ArmsRequest) -> dict:
    """Check arms for the Hardware values; `remember`: the action that remembers the boards of the arms
    found on the right port (None when there is none to remember). 409 while a robot command runs."""
    c = _context(ctx, req.hardware)
    result = ctx.jobs.check_arms(hardware.arms_to_check(c))
    return {**result, "remember": hardware.remember_checked(c, result)}
