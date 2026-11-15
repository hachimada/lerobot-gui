"""Shared helpers for the command builder tests (unit and contract)."""

from __future__ import annotations

from typing import ClassVar

from lerobot_gui import commands
from lerobot_gui.commands.context import Accounts, Context
from lerobot_gui.discovery import Discovery
from lerobot_gui.settings import Settings

CAMERAS = [
    {
        "name": "top",
        "type": "opencv",
        "device": "/dev/video0",
        "settings": {"width": 640, "height": 480, "fps": 30, "backend": "V4L2", "fourcc": "MJPG"},
    },
    {
        "name": "wrist",
        "type": "opencv",
        "device": "/dev/video2",
        "settings": {"width": 640, "height": 480, "fps": 30},
    },
]


def _setting(flag: str, kind: str, default=None, choices=None, required=False) -> dict:
    return {
        "flag": flag,
        "kind": kind,
        "default": default,
        "choices": choices,
        "required": required,
        "help": "",
        "type": kind,
    }


class FakeCameras:
    """A stand-in for lerobot's camera schema: an opencv-like type and a type without a device setting."""

    FIELDS: ClassVar[dict[str, tuple[dict, ...]]] = {
        "opencv": (
            _setting("fps", "int"),
            _setting("width", "int"),
            _setting("height", "int"),
            _setting("index_or_path", "str", required=True),
            _setting("rotation", "enum", "NO_ROTATION", ["NO_ROTATION", "ROTATE_90"]),
            _setting("fourcc", "str"),
            _setting("backend", "enum", "ANY", ["ANY", "V4L2"]),
        ),
        "remote": (
            _setting("fps", "int"),
            _setting("host", "str", required=True),
            _setting("name", "str", required=True),
        ),
    }

    def types(self):
        return tuple(self.FIELDS)

    def fields(self, cam_type):
        return self.FIELDS[cam_type]

    def device_field(self, cam_type):
        required = [f["flag"] for f in self.FIELDS[cam_type] if f["required"]]
        return required[0] if len(required) == 1 else None


#: the Hardware page as the user set it up
HARDWARE = {
    "followerPort": "/dev/ttyACM0",
    "followerId": "my_follower_arm",
    "leaderPort": "/dev/ttyACM1",
    "leaderId": "my_leader_arm",
    "cameras": CAMERAS,
}
LOGGED_IN = Accounts(
    loaded=True,
    hf={"logged_in": True, "user": "alice", "orgs": ["team"], "token_role": "write"},
)


def context(
    s: Settings,
    page: str,
    values: dict | None = None,
    *,
    hw: dict | None = None,
    accounts: Accounts | None = None,
    cameras=None,
) -> Context:
    stored = {"hardware": {**HARDWARE, **(hw or {})}}
    if values is not None:
        stored[page] = values
    return commands.make_context(
        Discovery(s).snapshot(),
        accounts or Accounts(),
        stored,
        root=s.root,
        hf_home=s.hf_home,
        page=page,
        cameras=cameras or FakeCameras(),
    )


def build(s: Settings, page: str, values: dict | None = None, *, listing=None, **kw):
    ctx = context(s, page, values, **kw)
    if listing is None:
        return commands.build(commands.get_page(page), ctx)
    return commands.build(commands.get_page(page), ctx, listing)


def flags(args: list[str]) -> dict[str, str]:
    return dict(a[2:].split("=", 1) for a in args if a.startswith("--"))


def option(flag: str, **more) -> dict:
    """One option as lerobot's listing has it (a text flag, unless `more` says otherwise)."""
    base = {"kind": "str", "choices": None, "default": None, "required": False, "optional": True, "type": "str"}
    return {"flag": flag, **base, "help": "", **more}


def listing(*options: dict, errors: tuple[str, ...] = ()):
    """A stand-in for lerobot's option listing with these options (flag, kind, default, ...)."""
    full = [option(**o) for o in options]
    return lambda *_query: {"options": full, "errors": list(errors)}
