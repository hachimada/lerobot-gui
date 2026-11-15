"""Setup pages: Environment, Calibrate, and the Find port / Find cameras commands run from Hardware."""

from __future__ import annotations

from ..adapters.roles import FOLLOWER, LEADER, ROLES, Role, other, types
from .context import Context, basename
from .model import Field, Group, Option, OptionsQuery, Page, is_set

ENVIRONMENT = Page(
    id="environment",
    title="Environment",
    icon="env",
    nav="Setup",
    desc=(
        "The environment the commands run in: they inherit the GUI's. lerobot's data dirs as lerobot "
        "resolves them, the environment variables that are set, and the lerobot that runs. A change to "
        "the environment takes effect when the GUI is restarted."
    ),
)

FIND_PORT = Page(
    # no page of its own: runs from the Find port card on the Hardware page
    id="find-port",
    title="Find port",
    icon="port",
    nav=None,
    exe="lerobot-find-port",
)

FIND_CAMERAS = Page(
    # no page of its own: runs from the Find cameras card on the Hardware page
    id="find-cameras",
    title="Find cameras",
    icon="camera",
    nav=None,
    exe="lerobot-find-cameras",
    options=lambda ctx: OptionsQuery(),
    groups=(
        Group(
            "Options",
            (
                # the arguments, their defaults and choices are read from lerobot-find-cameras itself
                Field(
                    "camera_type",
                    "Camera type",
                    "choice",
                    positional=True,
                    flag_label="camera_type",
                    lerobot_choices=True,
                ),
                Field("output-dir", "Output dir", "text", mono=True, help="Relative to the workspace."),
                Field("record-time-s", "Capture time (s)", "number", half=True),
            ),
        ),
    ),
)


def calibrate_role(ctx: Context) -> Role:
    return LEADER if ctx.v.get("gui.target") == LEADER.name else FOLLOWER


def _calibrate_help(ctx: Context) -> str | None:
    r = calibrate_role(ctx)
    arm_id, port = ctx.hw.get(r.id_key), ctx.hw.get(r.port_key)
    if not is_set(arm_id):
        return None
    if ctx.calibrated(r.calibration_kind, r.calibration_class, arm_id):
        return f"There is a calibration file for `{arm_id}`; the {r.name} is on `{basename(port)}`."
    return f"There is no calibration file for `{arm_id}` yet."


CALIBRATE = Page(
    id="calibrate",
    title="Calibrate",
    icon="calibrate",
    nav="Setup",
    exe="lerobot-calibrate",
    presets=True,
    desc="Runs `lerobot-calibrate` for one arm.",
    hw=lambda ctx: [calibrate_role(ctx).name],
    options=lambda ctx: OptionsQuery(types(calibrate_role(ctx))),
    # the other arm's flags don't apply
    option_filter=lambda flag, ctx: not flag.startswith(other(calibrate_role(ctx)).prefix + "."),
    groups=(
        Group(
            "Arm",
            (
                Field(
                    "gui.target",
                    "Arm to calibrate",
                    "seg",
                    default=FOLLOWER.name,
                    options=tuple(Option(r.name, r.label) for r in ROLES),
                    help=_calibrate_help,
                ),
            ),
        ),
    ),
)
