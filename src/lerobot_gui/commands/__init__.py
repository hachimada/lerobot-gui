"""Command pages: fields and the command line they build.

The frontend sends the values entered so far; `form()` answers with the page's fields (lerobot's
defaults and choices filled in from the installed lerobot), the command line and messages.
`build()` is the same without the fields, and is what Run executes, so the preview and the run
can't disagree. A flag is written only when its field has a value: lerobot checks the rest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import schemas
from ..adapters.roles import CAMERAS_FLAG
from ..discovery import Snapshot
from . import data, hardware, rollout, services, setup, train
from .cameras import cameras_arg
from .context import Accounts, CameraSchema, Context
from .domain import Args, arg_value, arm_args, as_bool, fmt_value, preview, to_number
from .extras import Listing, extra_args, options_query
from .model import Field, Messages, Option, Page, is_set, resolve

PAGES: tuple[Page, ...] = (
    setup.ENVIRONMENT,
    hardware.PAGE,
    setup.FIND_PORT,
    setup.FIND_CAMERAS,
    setup.CALIBRATE,
    data.TELEOPERATE,
    data.RECORD,
    train.PAGE,
    rollout.PAGE,
    services.HUGGINGFACE,
    services.TRACKIO,
)
BY_ID = {p.id: p for p in PAGES}
NAV = ("Setup", "Data", "Policy", "Services")


def get_page(page_id: str) -> Page:
    try:
        return BY_ID[page_id]
    except KeyError:
        raise ValueError(f"No page {page_id}") from None


def page_list() -> list[schemas.PageMeta]:
    from ..adapters.commands import COMMANDS

    return [
        {
            "id": p.id,
            "title": p.title,
            "icon": p.icon,
            "nav": p.nav,
            "exe": p.exe,
            "desc": p.desc,
            "hints": list(p.hints),
            # its command uses the robot or the cameras (one such command runs at a time)
            "hardware": bool(p.exe and COMMANDS.get(p.exe)),
            "presets": p.presets,
        }
        for p in PAGES
    ]


# ---------------------------------------------------------------- values


def resolve_values(page: Page, stored: dict[str, Any]) -> dict[str, Any]:
    """The values entered on `page`, plus its GUI choices (their default until one is picked)."""
    out = {k: v for k, v in stored.items() if is_set(v)}
    for f in page.fields():
        if not f.is_flag and f.key not in out:
            out[f.key] = f.default
    return out


def make_context(
    snap: Snapshot,
    accounts: Accounts,
    stored: dict[str, Any],
    *,
    root: Path,
    hf_home: Path,
    page: str = "",
    cameras: CameraSchema | None = None,
) -> Context:
    # values come from the browser as JSON: a page's values that aren't an object are dropped
    pages = {k: v for k, v in (stored or {}).items() if isinstance(v, dict)}
    ctx = Context(snap=snap, accounts=accounts, stored=pages, root=root, hf_home=hf_home, page=page, cameras=cameras)
    ctx.hw = hardware.values(pages.get("hardware", {}))
    ctx.v = resolve_values(get_page(page), pages.get(page, {})) if page else {}
    return ctx


# ------------------------------------------------------------------ build


def no_listing(_command: str, _selections: dict[str, str], _policy_path: str | None) -> dict | None:
    return None


def load_listing(page: Page, ctx: Context, listing: Listing) -> None:
    """Give the context the installed lerobot's options for the page's current selection."""
    query = ctx.options_query = options_query(page, ctx)
    found = listing(*query) if query else None
    ctx.listing = {o["flag"]: o for o in found["options"]} if found else None


def visible_fields(page: Page, ctx: Context) -> list[Field]:
    return [f for g in page.groups if g.visible(ctx) for f in g.fields if f.visible(ctx)]


def _write(f: Field, ctx: Context, a: Args, m: Messages) -> None:
    value = ctx.v.get(f.key)
    option = ctx.lerobot_option(f.key)
    if not is_set(value):
        if option and option.get("required"):
            m.err(f"{f.label} (`--{f.key}`) is required.")
        return
    if f.positional:
        a.append(arg_value(value))
    elif f.kind == "toggle":
        if as_bool(value) is True:  # off: the flag is left out
            a.flag(f.key, True)
    elif f.kind == "bool":
        b = as_bool(value)
        if b is None:
            m.err(f"{f.label}: `{fmt_value(value)}` is not true or false.")
        else:
            a.flag(f.key, b)
    elif f.kind == "number":
        n = to_number(value)
        integer = bool(option and option.get("kind") == "int")
        if n is None or (integer and not n.is_integer()):
            m.err(f"{f.label}: `{fmt_value(value)}` is not a valid {'integer' if integer else 'number'}.")
        else:
            a.flag(f.key, value)
    else:
        text = fmt_value(value)
        if f.convert:
            converted = f.convert(text, m, f.label)
            if converted is None:
                return
            text = converted
        a.flag(f.key, text)


def build(page: Page, ctx: Context, listing: Listing = no_listing) -> tuple[list[str], Messages]:
    """The command line for the values entered, and what is missing or malformed in them."""
    m = Messages()
    a = Args()
    if page.exe is None:
        return [], m
    load_listing(page, ctx, listing)
    parts = page.hardware_parts(ctx)
    hardware.hw_checks(ctx, m, parts)
    for part in parts:
        if part == "cameras":
            value = cameras_arg(ctx)
            if value is not None:
                a.flag(CAMERAS_FLAG, value)
        else:
            arm_args(ctx.hw, part, a)
    if page.extra_flags:
        a.extend(page.extra_flags(ctx))
    for f in visible_fields(page, ctx):
        if f.is_flag:
            _write(f, ctx, a, m)
    a.extend(extra_args(page, ctx, m))
    if page.check:
        page.check(ctx, m)
    return list(a), m


# ------------------------------------------------------------------- form


def _field_json(f: Field, ctx: Context) -> schemas.FieldSpec:
    option = ctx.lerobot_option(f.key) if f.is_flag else None
    opts = list(resolve(f.options, ctx) or ())
    if f.lerobot_choices and option and option.get("choices"):
        listed = list(option["choices"])
        opts = [Option(c) for c in listed] + [o for o in opts if not (isinstance(o, Option) and o.value in listed)]
    value = ctx.v.get(f.key)
    suggest = [x for x in (f.suggest(ctx) if f.suggest else []) if is_set(x) and x != value]
    flag = f.flag_label if f.flag_label is not None else f"--{f.key}" if f.is_flag else None
    # lerobot's default, unless it is an empty string (the field's example says more)
    default = f.default if not f.is_flag else (option.get("default") if option else None)
    return {
        "key": f.key,
        "label": f.label,
        "kind": f.kind,
        # a choice of the GUI itself (always has a value), not a lerobot flag
        "gui": not f.is_flag,
        "flag": flag,
        "value": value,
        # lerobot's default for an empty field (from the installed lerobot), or the GUI choice's default
        "default": default if default != "" else None,
        "required": bool(option and option.get("required")),
        "options": [o.to_json() for o in opts],
        # the GUI's own words about its choices, else lerobot's docstring of the flag
        "help": resolve(f.help, ctx) or (option.get("help") or None if option else None),
        "placeholder": resolve(f.placeholder, ctx),
        "custom": f.custom,
        "hub": f.hub,
        "mono": f.mono,
        "half": f.half,
        "advanced": f.advanced,
        "suggest": suggest[:6],
        # stored along with the value: {"values": {value: {key: value}}, "other": {key: value}}
        "also": f.also(ctx).to_json() if f.also else None,
    }


def form(
    page: Page, ctx: Context, listing: Listing = no_listing, *, preflight: schemas.ArmCheck | None = None
) -> schemas.FormResponse:
    args, m = build(page, ctx, listing)  # also loads the listing the fields show
    groups: list[schemas.GroupSpec] = []
    for g in page.groups:
        if not g.visible(ctx):
            continue
        fields = [_field_json(f, ctx) for f in g.fields if f.visible(ctx)]
        if fields:
            groups.append({"title": g.title, "fields": fields})
    parts = page.hardware_parts(ctx)
    command: schemas.CommandLine | None = None
    messages: list[schemas.Message] = []
    query = None
    if page.exe:
        command = {"exe": page.exe, "args": args, "preview": preview(page.exe, args)}
        messages = m.to_json()
        if preflight and preflight.get("swapped"):
            messages.insert(0, hardware.preflight_message(ctx, preflight))
        query = ctx.options_query
    return {
        "page": page.id,
        "groups": groups,
        "values": ctx.v,
        "hardware_summary": hardware.summary(ctx, parts) if parts else [],
        "command": command,
        "messages": messages,
        "errors": m.errors if page.exe else 0,
        "options_query": {"command": query[0], "selections": query[1], "policy_path": query[2]} if query else None,
        # lerobot's defaults and choices are shown once its options are listed
        "listing_ready": ctx.listing is not None,
    }
