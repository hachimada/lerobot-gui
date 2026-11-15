"""The Hardware page: its values (each arm's port, board and calibration id, the cameras) and the fields of
the arms. It isn't a command page: its values are the GUI's own, which the command pages write as flags."""

from __future__ import annotations

from typing import Any

from ... import schemas
from ...adapters.roles import FOLLOWER, ROLES, Role
from ..context import Context
from ..model import Also, Option, Page, is_set

PAGE = Page(
    id="hardware",
    title="Hardware",
    icon="hardware",
    nav="Setup",
    desc=(
        "Ports, arm ids and cameras used by every command, named as lerobot-find-port and lerobot-find-cameras "
        "report them. A port's number can change after replugging: each arm's board is remembered and a "
        "change is flagged. Cameras aren't followed: after replugging them, run Find cameras again."
    ),
)

#: what each value is until one is set: no board remembered, no cameras (a port or an id: none)
DEFAULTS: dict[str, Any] = {"cameras": [], **{r.board_key: None for r in ROLES}}


def values(stored: dict[str, Any]) -> dict[str, Any]:
    """The Hardware values as stored in the browser, with the defaults of those not set (and the cameras that
    aren't an object left out)."""
    out = {k: v for k, v in stored.items() if is_set(v)}
    for k, default in DEFAULTS.items():
        out.setdefault(k, list(default) if isinstance(default, list) else default)
    cams = out["cameras"] if isinstance(out["cameras"], list) else []
    out["cameras"] = [c for c in cams if isinstance(c, dict)]
    return out


def port_options(ctx: Context) -> list[Option]:
    out = []
    for tty in ctx.ttys():
        board = ctx.board_of(tty)
        out.append(Option(tty, f"{tty}  ·  board {ctx.board_label(board)}" if board else tty))
    return out


def port_board(ctx: Context, r: Role) -> Also:
    """The board stored with an arm's port: the one on the port chosen (any name of it), so a later
    renumbering is caught; none for a port without one, or one not plugged in."""
    found: dict[str, dict] = {}
    for p in ctx.snap.ports:
        if p["board"]:
            for name in (*p["aliases"], p["board"]):
                found.setdefault(name, {r.board_key: p["board"]})
    return Also(found, {r.board_key: None})


def calib_options(ctx: Context, r: Role) -> list[Option]:
    return [
        Option(c["id"]) for c in ctx.snap.calibrations.get(r.calibration_kind, []) if c["class"] == r.calibration_class
    ]


def _choice(
    ctx: Context,
    key: str,
    label: str,
    flag: str,
    options: list[Option],
    *,
    help: str | None = None,
    mono: bool = False,
    also: Also | None = None,
) -> schemas.FieldSpec:
    """A Hardware value chosen from what is found here, or typed. `flag`: the flag the commands write it as."""
    return {
        "key": key,
        "label": label,
        "kind": "choice",
        "gui": False,
        "flag": flag,
        "value": ctx.hw.get(key),
        "default": None,
        "required": False,
        "options": [o.to_json() for o in options],
        "help": help,
        "placeholder": "",
        "custom": True,
        "hub": False,
        "mono": mono,
        "half": False,
        "advanced": False,
        "suggest": [],
        "also": also.to_json() if also else None,
    }


def arm_fields(ctx: Context) -> list[schemas.GroupSpec]:
    """Each arm's port and calibration id."""
    port_help = (
        "As `lerobot-find-port` reports it. The number can change after replugging; the board is remembered and "
        "a change is flagged."
    )
    return [
        {
            "title": r.label,
            "fields": [
                _choice(
                    ctx,
                    r.port_key,
                    "Port",
                    f"--{r.flag('port')}",
                    port_options(ctx),
                    help=port_help if r is FOLLOWER else None,
                    mono=True,
                    also=port_board(ctx, r),
                ),
                _choice(ctx, r.id_key, "Id", f"--{r.flag('id')}", calib_options(ctx, r)),
            ],
        }
        for r in ROLES
    ]
