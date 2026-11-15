"""Everything the Hardware page shows besides its fields."""

from __future__ import annotations

from typing import cast

from ... import schemas
from ...adapters.roles import ROLES
from ..cameras import view as camera_view
from ..context import Context
from .checks import setup_status
from .guides import ARM_EXPLAIN, with_guides
from .page import arm_fields
from .ports import assign, confirm


def camera_name_suggestions(ctx: Context) -> list[str]:
    """Names offered as chips: the ones the trained policies and datasets expect."""
    names = [n for r in ctx.snap.policies for n in r.get("cameras") or []]
    names += [n for d in ctx.snap.datasets for n in d.get("cameras") or []]
    return list(dict.fromkeys(names))


def view(ctx: Context, arm_check: schemas.ArmCheck | None = None) -> schemas.HardwareView:
    """Everything the Hardware page shows besides its fields."""
    hw = ctx.hw
    ttys: list[schemas.Tty] = []
    for port in ctx.snap.ports:
        tty, board = port["tty"], port["board"]
        here = [r for r in ROLES if ctx.dev_of(hw.get(r.port_key)) == tty]
        ttys.append(
            {
                "tty": tty,
                "board": board,
                "serial": port["serial"],
                # the arms on this tty
                "roles": [r.name for r in here],
                # putting each other arm on it
                "assign": {r.name: assign(ctx, r, tty) for r in ROLES if r not in here},
                # an arm on it whose board isn't remembered yet can be confirmed
                "confirm": {r.name: confirm(ctx, r) for r in here if board and not hw.get(r.board_key)},
            }
        )
    cams = camera_view(ctx)
    return {
        "roles": [{"name": r.name, "label": r.label} for r in ROLES],
        "ttys": ttys,
        "camera_names": camera_name_suggestions(ctx),
        "status": setup_status(ctx, arm_check),
        "arm_check": with_guides(ctx, arm_check) if arm_check else None,
        "arm_explain": ARM_EXPLAIN,
        "calibrations": cast(schemas.Calibrations, ctx.snap.calibrations),
        "camera_types": cams["camera_types"],
        "camera_fields": cams["camera_fields"],
        "camera_device_field": cams["camera_device_field"],
    }


def form(ctx: Context, arm_check: schemas.ArmCheck | None = None) -> schemas.HardwareForm:
    """The Hardware page: the arms' fields, and everything else it shows."""
    return {"groups": arm_fields(ctx), "view": view(ctx, arm_check)}
