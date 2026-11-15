"""`--robot.cameras` from the Hardware page's cameras, with only the settings entered.

A camera on the Hardware page is the GUI's own entry: its name (the key in `--robot.cameras`),
lerobot's camera type, the device it uses, `use` (false: unchecked, not written) and
`settings`: lerobot's own settings of that type, as entered. The type's device setting (its one
required setting, e.g. `index_or_path`) is written from the device.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from .. import schemas
from .context import CameraSchema, Context
from .domain import fmt_value
from .model import is_set

_PLAIN = re.compile(r"^[A-Za-z0-9_./@+-]+$")


def schema(ctx: Context) -> CameraSchema:
    if ctx.cameras is None:
        from ..adapters.cameras import LEROBOT

        ctx.cameras = LEROBOT
    return ctx.cameras


def scalar(value: Any, *, key: bool = False) -> str:
    """A value inside `--robot.cameras`, which lerobot reads as YAML: text is quoted unless YAML reads it
    back as the same text (or, for a setting, as the number it spells). A camera name (`key`) is
    always text."""
    text = fmt_value(value)
    if not isinstance(value, str):
        return text
    if _PLAIN.match(text):
        import yaml

        read = yaml.safe_load(text)
        if read == text or (not key and type(read) in (int, float)):
            return text
    return json.dumps(text, ensure_ascii=False)


def used(hw: dict) -> list[dict]:
    """The cameras the commands use: the Hardware page's cameras, without the unchecked ones."""
    return [c for c in hw.get("cameras") or [] if isinstance(c, dict) and c.get("use") is not False]


def label(cam: dict) -> str:
    """A camera in a message: by its name, else by its device."""
    if is_set(cam.get("name")):
        return f"Camera `{cam['name']}`"
    if is_set(cam.get("device")):
        return f"The camera on `{cam['device']}`"
    return "A camera"


def camera_entries(ctx: Context, cam: dict) -> list[tuple[str, Any]] | None:
    """(setting, value) pairs of one camera, type first; None without a type the installed lerobot has (the
    Hardware checks say so)."""
    cam_type = str(cam.get("type") or "")
    cams = schema(ctx)
    if cam_type not in cams.types():
        return None
    device = cams.device_field(cam_type)
    raw = cam.get("settings")
    settings: dict = raw if isinstance(raw, dict) else {}
    entries: list[tuple[str, Any]] = [("type", cam_type)]
    for f in cams.fields(cam_type):
        key = f["flag"]
        value = cam.get("device") if key == device else settings.get(key)
        if is_set(value):
            entries.append((key, value))
    return entries


def cameras_arg(ctx: Context) -> str | None:
    """The `--robot.cameras` value of the cameras used, or None without any."""
    cams = used(ctx.hw)
    if not cams:
        return None
    parts = []
    for cam in cams:
        if not is_set(cam.get("name")):
            continue  # the Hardware checks ask for its name
        entries = camera_entries(ctx, cam)
        if entries is not None:
            inner = ", ".join(f"{k}: {scalar(v)}" for k, v in entries)
            parts.append(f"{scalar(str(cam.get('name') or ''), key=True)}: {{{inner}}}")
    return "{" + ", ".join(parts) + "}"


def field_json(option: dict) -> schemas.FieldSpec:
    """A lerobot setting as a field of the Hardware page's camera settings."""
    kinds: dict[str, schemas.FieldKind] = {
        "bool": "bool",
        "int": "number",
        "float": "number",
        "enum": "choice",
        "choice": "choice",
    }
    kind = kinds.get(option["kind"], "text")
    return {
        "key": option["flag"],
        "label": option["flag"],
        "kind": kind,
        "gui": False,
        "flag": option.get("type"),
        "value": None,
        "default": option.get("default") if option.get("default") != "" else None,
        "required": bool(option.get("required")),
        "options": [{"value": c, "label": c, "disabled": False, "title": ""} for c in option.get("choices") or []],
        "help": option.get("help") or None,
        "placeholder": "",
        "custom": False,
        "hub": False,
        "mono": kind == "text",
        "half": kind in ("number", "bool", "choice"),
        "advanced": False,
        "suggest": [],
        "also": None,
    }


class CameraView(TypedDict):
    camera_types: list[str]
    camera_fields: dict[str, list[schemas.FieldSpec]]
    camera_device_field: dict[str, str | None]


def view(ctx: Context) -> CameraView:
    """What the Hardware page needs to edit cameras: the types, their settings and device settings."""
    cams = schema(ctx)
    types = list(cams.types())
    return {
        "camera_types": types,
        "camera_fields": {t: [field_json(o) for o in cams.fields(t)] for t in types},
        "camera_device_field": {t: cams.device_field(t) for t in types},
    }
