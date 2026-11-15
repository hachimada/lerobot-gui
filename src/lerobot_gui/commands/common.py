"""What several pages share: their texts, fields and the choices they offer."""

from __future__ import annotations

from .context import Context
from .model import Field, Option, OptionGroup

#: the hints of the pages whose command drives the follower (the arm check before it starts)
ARM_CHECK_HINTS = (
    "Before it starts, the arms are checked: if a port's motors hold the other arm's calibration (swapped ports), "
    "it doesn't run.",
)


def max_rel_field() -> Field:
    return Field(
        "robot.max_relative_target",
        "Max relative target",
        "number",
        half=True,
    )


def namespaces(ctx: Context) -> list[str]:
    """Repo-id namespaces offered as chips (`alice/`): the account's, its organizations' and the local ones."""
    return [f"{n}/" for n in ctx.hf_namespaces()]


def device_options(ctx: Context) -> list[Option | OptionGroup]:
    """The devices this computer has (torch); the field also takes another."""
    from ..adapters.torch_devices import available

    return [Option(d["value"], d["label"]) for d in available()]
