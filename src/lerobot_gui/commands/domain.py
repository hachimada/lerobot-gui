"""Helpers the pages share to write their flags. No knowledge of what lerobot accepts: lerobot
checks its own arguments when the command runs."""

from __future__ import annotations

import json
import re
import shlex
from typing import Any

from ..adapters.roles import role
from ..paths import expand
from .model import Messages, is_set


def fmt_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def to_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        n = float(str(value).strip())
    except ValueError:
        return None
    return n if n == n and n not in (float("inf"), float("-inf")) else None


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return {"true": True, "false": False}.get(text)


def arg_value(value: Any) -> str:
    """A value as the command gets it: a leading `~` is the home dir (no shell expands it)."""
    return expand(fmt_value(value))


class Args(list[str]):
    """The command line under construction."""

    def flag(self, name: str, value: Any) -> None:
        self.append(f"--{name}={arg_value(value)}")


# ------------------------------------------------------------ hardware flags


def arm_args(hw: dict, name: str, a: Args) -> None:
    """--robot.* for the follower, --teleop.* for the leader, from the Hardware page."""
    r = role(name)
    a.flag(r.flag("type"), r.type)
    if is_set(hw.get(r.port_key)):
        a.flag(r.flag("port"), hw[r.port_key])
    if is_set(hw.get(r.id_key)):
        a.flag(r.flag("id"), hw[r.id_key])


# ------------------------------------------------- converting typed input


def json_map(text: str, m: Messages, label: str) -> str | None:
    """A JSON object typed into a field, written the way lerobot reads it."""
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        m.err(f'{label}: must be a JSON object, e.g. `{{"observation.images.top": "observation.images.camera1"}}`.')
        return None
    return "{" + ", ".join(f"{json.dumps(k)}: {json.dumps(v)}" for k, v in data.items()) + "}"


def episode_list(text: str, m: Messages, label: str) -> str | None:
    """`0-3,7` -> `[0,1,2,3,7]`; a list is passed on as it is."""
    if text.strip().startswith("["):
        return text.strip()
    out: set[int] = set()
    for part in filter(None, re.split(r"[\s,]+", text)):
        mm = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        a = int(mm.group(1)) if mm else 0
        b = int(mm.group(2)) if mm and mm.group(2) is not None else a
        if not mm or b < a or b - a > 100_000:
            m.err(f"{label}: use e.g. `0-39`, `0,1,2` or `[0,1,2]`.")
            return None
        out.update(range(a, b + 1))
    return "[" + ",".join(map(str, sorted(out))) + "]"


# ------------------------------------------------------------------ preview

_SAFE = re.compile(r"^[A-Za-z0-9_@%+=:,./-]+$")


def quote(s: str) -> str:
    if s == "":
        return "''"
    if _SAFE.match(s):
        return s
    if not re.search(r"[\"$`\\!]", s):
        return f'"{s}"'
    return shlex.quote(s)


def quote_arg(a: str) -> str:
    mm = re.match(r"^(--[^=\s]+)=([\s\S]*)$", a)
    return f"{mm.group(1)}={quote(mm.group(2))}" if mm else quote(a)


def preview(exe: str, args: list[str]) -> str:
    """The command as a shell line to copy (run from the workspace, like the GUI does)."""
    return f"uv run {exe}" + "".join(f" \\\n    {quote_arg(a)}" for a in args)


def fmt_step(s: Any) -> str:
    return f"{int(s):,}" if str(s).isdigit() else str(s)
