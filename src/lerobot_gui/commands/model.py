"""The building blocks of a page: fields, groups, messages and the actions they offer.

A field is one lerobot flag: its key is the flag without `--` (e.g. `dataset.repo_id`), and the
values a page stores are keyed the same way, so the curated fields and "All options" share them.
A flag goes into the command only when the user entered a value; an empty field leaves it to
lerobot's default, which is read from the installed lerobot and shown as a placeholder.

Keys starting with `gui.` are the GUI's own choices (which arm to calibrate, how a training run
starts, whether to pass the Hardware cameras or leader): they decide which flags a page writes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .. import schemas
from ..schemas import Action, FieldKind, Level

if TYPE_CHECKING:
    from .context import Context

#: a value, or a function of the context that gives it
type Dyn[T] = T | Callable[[Context], T]

GUI = "gui."


def resolve[T](x: Dyn[T], ctx: Context) -> T:
    return x(ctx) if callable(x) else x  # type: ignore[return-value]


def is_set(x: Any) -> bool:
    return x is not None and x != ""


# ------------------------------------------------------------------ fields


@dataclass(frozen=True)
class Option:
    value: str
    label: str = ""
    disabled: bool = False
    title: str = ""

    def to_json(self) -> schemas.Option:
        return {"value": self.value, "label": self.label or self.value, "disabled": self.disabled, "title": self.title}


@dataclass(frozen=True)
class OptionGroup:
    group: str
    items: tuple[Option, ...]

    def to_json(self) -> schemas.OptionGroup:
        return {"group": self.group, "items": [o.to_json() for o in self.items]}


def options(*values: str) -> tuple[Option, ...]:
    return tuple(Option(v) for v in values)


@dataclass(frozen=True)
class Also:
    """Values stored along with a field's when it is set: `values[v]` for the value `v`, else `other`."""

    values: dict[str, dict]
    other: dict

    def to_json(self) -> schemas.Also:
        return {"values": self.values, "other": self.other}


@dataclass(frozen=True)
class Field:
    #: the lerobot flag without `--`, or `gui.<name>` for a choice of the GUI itself
    key: str
    label: str
    kind: FieldKind
    #: choices offered (choice, seg); with `lerobot_choices` they come after lerobot's own
    options: Dyn[Sequence[Option | OptionGroup]] = ()
    #: choice: offer the choices lerobot lists for this flag (choice types, enums)
    lerobot_choices: bool = False
    show: Callable[[Context], bool] | None = None
    help: Dyn[str | None] = None
    #: an example, shown when lerobot has no default to show
    placeholder: Dyn[str] = ""
    #: choice: also takes a typed value
    custom: bool = False
    mono: bool = False
    half: bool = False
    advanced: bool = False
    #: values offered as one-click chips
    suggest: Callable[[Context], list[str]] | None = None
    #: GUI choices only: the choice until the user picks one
    default: Any = None
    #: what is shown as the flag when it isn't `--<key>` (GUI choices, positional arguments)
    flag_label: str | None = None
    #: a positional argument instead of `--key=value`
    positional: bool = False
    #: turns the typed text into the flag's value; None when it can't (an error is reported)
    convert: Callable[[str, Messages, str], str | None] | None = None
    #: picker: models on the Hugging Face Hub are offered too
    hub: bool = False
    #: lerobot lists it among the command's config options (`--policy.path` and `--config_path` are
    #: read by lerobot's parser before the config, so they aren't)
    listed: bool = True
    #: values stored along with the field's (a Hardware port: the board on it)
    also: Callable[[Context], Also] | None = None

    @property
    def is_flag(self) -> bool:
        return not self.key.startswith(GUI)

    def visible(self, ctx: Context) -> bool:
        if self.show is not None and not self.show(ctx):
            return False
        # a flag the installed lerobot doesn't list for the current selection doesn't apply
        listing = ctx.listing
        return not (
            listing is not None and self.is_flag and self.listed and not self.positional and self.key not in listing
        )


@dataclass(frozen=True)
class Group:
    title: str
    fields: tuple[Field, ...]
    show: Callable[[Context], bool] | None = None

    def visible(self, ctx: Context) -> bool:
        return self.show is None or bool(self.show(ctx))


# ------------------------------------------------------- messages, actions
# what a message's button does in the frontend: schemas.Action


def go(page: str, label: str) -> schemas.GoAction:
    return {"type": "go", "page": page, "label": label}


def set_values(
    page: str,
    values: dict,
    label: str,
    go: str | None = None,
    *,
    toast: str | None = None,
) -> schemas.SetAction:
    action: schemas.SetAction = {"type": "set", "page": page, "values": values, "label": label}
    if go:
        action["go"] = go
    if toast:
        action["toast"] = toast
    return action


def set_hardware(
    values: dict, label: str, *, toast: str | None = None, keep_check: bool = False
) -> schemas.HardwareAction:
    """Change Hardware values; the Check arms result goes, unless the change moves no arm (`keep_check`)."""
    action: schemas.HardwareAction = {"type": "hardware", "values": values, "label": label}
    if toast:
        action["toast"] = toast
    if keep_check:
        action["keep_check"] = True
    return action


def check_arms(label: str = "Check arms") -> schemas.CheckArmsAction:
    return {"type": "check_arms", "label": label}


def scroll(target: str, label: str) -> schemas.ScrollAction:
    return {"type": "scroll", "target": target, "label": label}


OPEN_HARDWARE = go("hardware", "Open Hardware")
OPEN_HF = go("huggingface", "Log in to Hugging Face")


@dataclass
class Message:
    level: Level
    text: str
    actions: list[Action] = field(default_factory=list)

    def to_json(self) -> schemas.Message:
        return {"level": self.level, "text": self.text, "actions": self.actions}


class Messages:
    """What the builder has to say: errors (missing or malformed input) block Run."""

    def __init__(self) -> None:
        self.items: list[Message] = []

    def _add(self, level: Level, text: str, actions: tuple[Action | None, ...]) -> None:
        self.items.append(Message(level, text, [a for a in actions if a]))

    def err(self, text: str, *actions: Action | None) -> None:
        self._add("err", text, actions)

    def warn(self, text: str, *actions: Action | None) -> None:
        self._add("warn", text, actions)

    def info(self, text: str, *actions: Action | None) -> None:
        self._add("info", text, actions)

    @property
    def errors(self) -> int:
        return sum(m.level == "err" for m in self.items)

    def texts(self, level: Level | None = None) -> list[str]:
        return [m.text for m in self.items if level is None or m.level == level]

    def to_json(self) -> list[schemas.Message]:
        # in the order said: the frontend shows errors first (Alerts)
        return [m.to_json() for m in self.items]


# -------------------------------------------------------------------- pages


@dataclass(frozen=True)
class OptionsQuery:
    """Which `--help` options apply: the selected choice types and the policy to read defaults from."""

    selections: dict[str, str] = field(default_factory=dict)
    policy_path: str | None = None


@dataclass(frozen=True)
class Page:
    id: str
    title: str
    icon: str
    #: sidebar section, or None for commands run from another page (find-port, find-cameras)
    nav: str | None
    exe: str | None = None
    desc: str = ""
    groups: tuple[Group, ...] = ()
    #: its values can be saved under a name (the command pages)
    presets: bool = False
    hints: tuple[str, ...] = ()
    #: the Hardware it uses ("follower", "leader", "cameras"): summarized, checked, written as flags
    hw: Callable[[Context], Sequence[str | None]] | None = None
    #: flags the page writes besides its fields (positional arguments, `--resume` of a resumed run)
    extra_flags: Callable[[Context], list[str]] | None = None
    #: warnings about the GUI's own state (the login for Push to Hub / Trackio Spaces)
    check: Callable[[Context, Messages], None] | None = None
    #: the "All options" listing for the current values
    options: Callable[[Context], OptionsQuery] | None = None
    #: flags written by the page, never offered in "All options"
    handled: tuple[str, ...] = ()
    #: False hides an option of the listing (it belongs to something the page doesn't use)
    option_filter: Callable[[str, Context], bool] | None = None

    def fields(self) -> list[Field]:
        return [f for g in self.groups for f in g.fields]

    def hardware_parts(self, ctx: Context) -> list[str]:
        """The parts of the Hardware page its command uses now (`hw` without the ones it doesn't)."""
        return [p for p in (self.hw(ctx) if self.hw else []) if p]
