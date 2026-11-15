"""What an arm's port choice stores: the port and the board on it, so a renumbering after replugging is
caught and followed; assigning, swapping and confirming a port; the boards Check arms remembers."""

from __future__ import annotations

from collections.abc import Sequence

from ...adapters.roles import FOLLOWER, LEADER, ROLES, Role, other, role
from ...schemas import HardwareAction
from ..context import Context
from ..model import is_set, set_hardware


def arm_moves(ctx: Context) -> list[dict]:
    """Arms whose remembered board is now on another tty (now=None: not plugged in)."""
    out = []
    for r in ROLES:
        board = ctx.hw.get(r.board_key)
        if not board:
            continue
        now = ctx.tty_of_board(board)
        if now != ctx.dev_of(ctx.hw.get(r.port_key)):
            out.append({"role": r, "board": board, "now": now})
    return out


def follow_patch(ctx: Context) -> dict:
    """Hardware values that move the arms to the ports their boards are on now."""
    patch: dict = {}
    for m in arm_moves(ctx):
        if m["now"]:
            patch[m["role"].port_key] = m["now"]
            patch[m["role"].board_key] = m["board"]
    return patch


def follow(ctx: Context, label: str) -> HardwareAction:
    return set_hardware(follow_patch(ctx), label)


def assign(ctx: Context, r: Role, tty: str) -> HardwareAction:
    """Put arm `r` on the port `tty`, remembering the board on it. When the other arm is on that port,
    it gets `r`'s port (they swap)."""
    hw, o = ctx.hw, other(r)
    mine = hw.get(r.port_key)
    patch = {r.port_key: ctx.dev_of(tty), r.board_key: ctx.board_of(tty)}
    swapped = ctx.dev_of(hw.get(o.port_key)) == ctx.dev_of(tty)
    if swapped:
        patch |= {o.port_key: ctx.dev_of(mine), o.board_key: ctx.board_of(mine)}
    toast = f"Swapped: {r.name} ↔ {o.name}" if swapped else f"{r.name} → {tty}"
    return set_hardware(patch, r.label, toast=toast)


def confirm(ctx: Context, r: Role) -> HardwareAction:
    """Remember the board on arm `r`'s port: the user says it is that arm (the arm check isn't needed)."""
    return set_hardware(remember_boards(ctx, [r.name]), f"Confirm {r.name}", keep_check=True)


def swap_ports(ctx: Context, label: str) -> HardwareAction:
    """Each arm on the other's port, with the board on it."""
    follower, leader = ctx.hw.get(FOLLOWER.port_key), ctx.hw.get(LEADER.port_key)
    return set_hardware(
        {
            FOLLOWER.port_key: ctx.dev_of(leader),
            FOLLOWER.board_key: ctx.board_of(leader),
            LEADER.port_key: ctx.dev_of(follower),
            LEADER.board_key: ctx.board_of(follower),
        },
        label,
    )


def arms_to_check(ctx: Context) -> list[dict]:
    """The arms Check arms reads: each one with a port and an id on the Hardware page."""
    hw = ctx.hw
    return [
        {"role": r.name, "port": str(hw[r.port_key]), "id": str(hw[r.id_key])}
        for r in ROLES
        if is_set(hw.get(r.port_key)) and is_set(hw.get(r.id_key))
    ]


def remember_boards(ctx: Context, names: Sequence[str]) -> dict:
    """Hardware values that remember the board on each of these arms' ports (a port without one is left)."""
    patch: dict = {}
    for name in names:
        r = role(name)
        port = ctx.hw.get(r.port_key)
        board = ctx.board_of(port)
        if board:
            patch[r.port_key] = ctx.dev_of(port)
            patch[r.board_key] = board
    return patch


def remember_checked(ctx: Context, result: dict) -> HardwareAction | None:
    """After Check arms: remember the board of each arm whose motors hold its own calibration (so it is on
    the right port) and whose board isn't remembered yet."""
    verified = [
        a["role"] for a in result.get("arms", []) if a["status"] == "ok" and not ctx.hw.get(role(a["role"]).board_key)
    ]
    patch = remember_boards(ctx, verified)
    if not patch:
        return None
    names = " and ".join(r.name for r in ROLES if r.board_key in patch)
    return set_hardware(patch, "Remember the boards", toast=f"Remembered the board of the {names}", keep_check=True)
