"""Local training runs as policy candidates (the Hub's are listed by the frontend from /api/hub/models)."""

from __future__ import annotations

from .context import Context
from .domain import fmt_step
from .model import Option, OptionGroup


def run_label(run: dict) -> str:
    """The policy type of a run (its folder names the run)."""
    return str(run.get("type") or "?")


def local_policies(ctx: Context) -> list[Option | OptionGroup]:
    """Each training run's checkpoints (their `pretrained_model` dirs), newest run first."""
    return [
        OptionGroup(
            r["dir"],
            (
                Option(r["last"], f"{run_label(r)} · last (step {fmt_step(r['last_step'])})"),
                *(Option(s["path"], f"{run_label(r)} · step {fmt_step(s['step'])}") for s in r["steps"]),
            ),
        )
        for r in ctx.snap.policies
    ]
