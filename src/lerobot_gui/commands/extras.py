""" "All options": every `--help` option of the command that the page's own fields don't cover.

Values typed there are stored with the page's other values, keyed by flag. They are written only
when the installed lerobot lists the flag for the current selection; the others are kept, unsaid,
so a selection changed back brings them back (what is written is what the page and the command show).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..adapters.roles import CAMERAS_FLAG, ROLES
from ..paths import expand
from .context import Context
from .domain import arg_value, to_number
from .model import GUI, Messages, OptionsQuery, Page, is_set

#: flags every page writes from the Hardware page
HW_FLAGS = frozenset({r.flag(f) for r in ROLES for f in ("type", "port", "id")} | {CAMERAS_FLAG})

#: (command, selections, policy_path) -> the option listing, or None while it isn't available
Listing = Callable[[str, dict[str, str], str | None], dict | None]


def options_query(page: Page, ctx: Context) -> tuple[str, dict[str, str], str | None] | None:
    """What to list for the page: the command, its choice selections (any `.type` value counts) and policy."""
    if page.options is None or page.exe is None:
        return None
    q: OptionsQuery = page.options(ctx)
    selections = {k: v for k, v in q.selections.items() if v}
    for flag, value in ctx.v.items():
        if flag.endswith(".type") and not flag.startswith(GUI) and is_set(value) and flag not in page.handled:
            selections[flag.removesuffix(".type")] = str(value)
    path = expand(q.policy_path) if q.policy_path else None
    if path and not Path(path).is_absolute() and (ctx.root / path).exists():
        path = str(ctx.root / path)  # a local checkpoint, relative to the workspace
    return page.exe, selections, path


def handled_flags(page: Page) -> set[str]:
    """Flags the page writes itself: never offered in All options."""
    return set(HW_FLAGS) | set(page.handled) | {f.key for f in page.fields() if f.is_flag}


def visible(page: Page, ctx: Context, handled: set[str], flag: str) -> bool:
    return flag not in handled and (page.option_filter is None or page.option_filter(flag, ctx))


def visible_options(page: Page, ctx: Context, listing: dict) -> list[dict]:
    handled = handled_flags(page)
    return [o for o in listing["options"] if visible(page, ctx, handled, o["flag"])]


def extras_of(page: Page, ctx: Context) -> dict[str, str]:
    """Values entered in All options: the page's values that aren't one of its fields."""
    own = {f.key for f in page.fields()}
    return {k: str(v) for k, v in ctx.v.items() if k not in own and not k.startswith(GUI) and is_set(v)}


def extra_args(page: Page, ctx: Context, m: Messages) -> list[str]:
    extras = extras_of(page, ctx)
    if not extras:
        return []
    handled = handled_flags(page)
    known = ctx.listing
    args = []
    for flag, value in extras.items():
        o = known.get(flag) if known is not None else None
        if flag in handled or (known is not None and (o is None or not visible(page, ctx, handled, flag))):
            continue  # not an option of the current selection: kept, not written
        if o and o["kind"] in ("int", "float"):
            n = to_number(value)
            if n is None or (o["kind"] == "int" and not n.is_integer()):
                m.err(f"`--{flag}`: `{value}` is not a valid {o['kind']}.")
                continue
        args.append(f"--{flag}={arg_value(value)}")
    if known is None:
        m.info("Checking the extra options against lerobot…")
    return args
