"""The Hardware checks, made once: a command page says the problems of the parts it uses, the Hardware
page's Setup status lists them all. And the chips at the top of a command page."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal

from ... import schemas
from ...adapters.arms import arm_line
from ...adapters.roles import FOLLOWER, LEADER, ROLES, Role
from ..cameras import label as camera_label
from ..cameras import schema, used
from ..context import Context, basename
from ..model import OPEN_HARDWARE, Action, Messages, check_arms, is_set, scroll
from .ports import follow


def same_port(ctx: Context) -> bool:
    """Whether the follower and the leader are set to the same port."""
    port = ctx.hw.get(FOLLOWER.port_key)
    return is_set(port) and ctx.dev_of(port) == ctx.dev_of(ctx.hw.get(LEADER.port_key))


#: the card of each Hardware step, for "Go to step n"
STEP_CARDS = {2: "arms-card", 3: "cameras-card", 4: "camsettings-card"}


@dataclass(frozen=True)
class Finding:
    """One result of the Hardware checks, worded for both places that show it: a command page says the
    problems of the parts it uses, the Hardware page's Setup status lists them all."""

    level: Literal["ok", "warn", "err"]
    text: str
    #: not set yet: a to-do on the Hardware page (a command page says it at `level`)
    todo: bool = False
    #: the Hardware step that fixes it: Open Hardware on a command page, Go to step n on the Hardware page
    step: int | None = None
    #: a fix that works on any page, instead of the step
    fix: Action | None = None
    #: advice for the Hardware page only
    hardware_only: bool = False


def arm_findings(ctx: Context, r: Role) -> list[Finding]:
    """Whether arm `r` is set, still where it was assigned, and has a calibration file."""
    port, arm_id, board = ctx.hw.get(r.port_key), ctx.hw.get(r.id_key), ctx.hw.get(r.board_key)
    now = ctx.tty_of_board(board) if board else None
    out: list[Finding] = []
    if not is_set(port):
        out.append(Finding("err", f"Set the {r.name} port.", todo=True, step=2))
    elif board and not now:
        out.append(Finding("warn", f"{r.label}'s board (`{ctx.board_label(board)}`) is not plugged in."))
    elif board and now != ctx.dev_of(port):
        out.append(
            Finding(
                "err",
                f"{r.label}: its board (`{ctx.board_label(board)}`) is now `{now}`, not `{port}`. "
                "The port numbers changed after replugging.",
                fix=follow(ctx, f"Use {now}"),
            )
        )
    elif not ctx.port_connected(port):
        out.append(Finding("warn", f"{r.label} port `{port}` is not plugged in."))
    elif board:
        out.append(Finding("ok", f"{r.label} on `{ctx.dev_of(port)}` (board `{ctx.board_label(board)}`)."))
    else:
        out.append(
            Finding(
                "warn",
                f"{r.label} on `{port}`, board not recorded yet. Check arms records it once the arm checks out (or "
                "Confirm it in step 2), so a renumbering is caught.",
                fix=check_arms(),
                hardware_only=True,
            )
        )
    if is_set(arm_id):
        if ctx.calibrated(r.calibration_kind, r.calibration_class, arm_id):
            out.append(Finding("ok", f"{r.label} calibration file `{arm_id}`."))
        else:
            out.append(
                Finding("warn", f"No calibration file for {r.name} id `{arm_id}` (check the id for typos).", step=2)
            )
    return out


def camera_findings(ctx: Context) -> list[Finding]:
    """Whether the cameras used can be written: named once each, with a type lerobot has and its device."""
    cams = used(ctx.hw)
    if not cams:
        return [Finding("warn", "No cameras used yet: run Find cameras and check the ones to use.", todo=True, step=3)]
    out: list[Finding] = []
    # any name: --robot.cameras quotes it (whether lerobot takes it is lerobot's to say)
    names = [c["name"] for c in cams if is_set(c.get("name"))]
    if len(set(names)) != len(names):
        out.append(Finding("err", "Camera names must be unique.", step=3))
    types = schema(ctx)
    for cam in cams:
        before = len(out)
        who, device, cam_type = camera_label(cam), cam.get("device"), str(cam.get("type") or "")
        if not is_set(cam.get("name")):
            out.append(Finding("err", f"{who}: give it a name.", todo=True, step=3))
        if not cam_type:
            out.append(Finding("err", f"{who}: choose its type.", todo=True, step=4))
        elif cam_type not in types.types():
            out.append(Finding("err", f"{who}: the installed lerobot has no camera type `{cam_type}`.", step=4))
        elif types.device_field(cam_type) is not None and not is_set(device):
            out.append(Finding("err", f"{who} has no device.", todo=True, step=4))
        if len(out) == before:
            out.append(Finding("ok", f"{who} on `{device}`." if is_set(device) else f"{who}."))
    return out


def findings(ctx: Context, parts: Collection[str] | None = None) -> list[Finding]:
    """The Hardware checks: all of them, or those of the parts a command uses (`parts`)."""

    def uses(*about: str) -> bool:
        return parts is None or all(p in parts for p in about)

    out = [f for r in ROLES if uses(r.name) for f in arm_findings(ctx, r)]
    if uses(*(r.name for r in ROLES)) and same_port(ctx):
        out.append(Finding("err", "Follower and leader use the same port.", step=2))
    if uses("cameras"):
        out += camera_findings(ctx)
    return out


def hw_checks(ctx: Context, m: Messages, parts: Sequence[str]) -> None:
    """A command page's messages: the problems of the Hardware it uses."""
    for f in findings(ctx, parts):
        if f.level != "ok" and not f.hardware_only:
            (m.err if f.level == "err" else m.warn)(f.text, f.fix or (OPEN_HARDWARE if f.step else None))


def arm_check_findings(arm_check: schemas.ArmCheck | None) -> list[Finding]:
    """What Check arms found (on the Hardware page)."""
    if not arm_check:
        text = "Arms not checked yet: Check arms confirms which arm is on each port."
        return [Finding("warn", text, todo=True, fix=check_arms(), hardware_only=True)]
    out = []
    for a in arm_check.get("arms", []):
        level = "ok" if a["status"] == "ok" else "err" if a["status"] in ("other", "error") else "warn"
        fix = None if level == "ok" else scroll("arms-card", "What to do (step 2)")
        out.append(Finding(level, arm_line(a), fix=fix, hardware_only=True))
    return out


def setup_status(ctx: Context, arm_check: schemas.ArmCheck | None = None) -> list[schemas.StatusItem]:
    """The right column of the Hardware page: every check, ready or not, and what Check arms found."""
    arms = findings(ctx, [r.name for r in ROLES])
    items = []
    for f in (*arms, *arm_check_findings(arm_check), *camera_findings(ctx)):
        action = f.fix or (scroll(STEP_CARDS[f.step], f"Go to step {f.step}") if f.step else None)
        items.append({"level": "todo" if f.todo else f.level, "text": f.text, "actions": [action] if action else []})
    return items


def summary(ctx: Context, parts: Sequence[str]) -> list[schemas.SummaryChip]:
    """The chips at the top of a command page: which arms and cameras it will use."""
    hw = ctx.hw
    chips = []
    for r in ROLES:
        if r.name in parts:
            value = " · ".join(str(x) for x in (basename(hw.get(r.port_key)), hw.get(r.id_key)) if is_set(x))
            chips.append({"label": r.label, "value": value or "not set"})
    if "cameras" in parts:
        cams = "  ".join(f"{c.get('name') or '?'}={basename(c.get('device')) or '?'}" for c in used(hw))
        chips.append({"label": "Cameras", "value": cams or "none"})
    return chips
