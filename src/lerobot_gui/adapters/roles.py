"""The two arms the GUI sets up, and what lerobot calls them: their flags, type and calibration folder.

The follower is lerobot's robot (`--robot.*`), the leader its teleoperator (`--teleop.*`), both
SO-101 arms. The Hardware page keeps each arm's values under `<name>Port`, `<name>Id` and
`<name>Board` (the USB-serial board last seen on its port). Everything else that names an arm
reads it from here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    #: the GUI's name of the arm, as pages, messages and stored values use it
    name: str
    label: str
    #: the arm's flags are `--<prefix>.<field>`
    prefix: str
    #: the lerobot type the commands write
    type: str
    #: the types whose motors the arm check reads (SO-100 and SO-101 arms have the same motors)
    checked_types: tuple[str, ...]
    #: lerobot's calibration folder of the arm (a key of `Settings.calibration`), and the folder of
    #: its class in it: <folder>/<class>/<id>.json
    calibration_kind: str
    calibration_class: str

    def flag(self, field: str) -> str:
        return f"{self.prefix}.{field}"

    @property
    def port_key(self) -> str:
        return f"{self.name}Port"

    @property
    def id_key(self) -> str:
        return f"{self.name}Id"

    @property
    def board_key(self) -> str:
        return f"{self.name}Board"


FOLLOWER = Role(
    name="follower",
    label="Follower",
    prefix="robot",
    type="so101_follower",
    checked_types=("so101_follower", "so100_follower"),
    calibration_kind="robots",
    calibration_class="so_follower",
)
LEADER = Role(
    name="leader",
    label="Leader",
    prefix="teleop",
    type="so101_leader",
    checked_types=("so101_leader", "so100_leader"),
    calibration_kind="teleoperators",
    calibration_class="so_leader",
)
ROLES: tuple[Role, ...] = (FOLLOWER, LEADER)
_BY_NAME = {r.name: r for r in ROLES}

#: the flag of the cameras (they belong to the robot)
CAMERAS_FLAG = FOLLOWER.flag("cameras")


def role(name: str) -> Role:
    """The role named `name` ("follower" or "leader")."""
    try:
        return _BY_NAME[name]
    except KeyError:
        raise ValueError(f"No arm role {name!r}") from None


def other(r: Role) -> Role:
    """The other arm."""
    return LEADER if r is FOLLOWER else FOLLOWER


def types(*roles: Role) -> dict[str, str]:
    """{prefix: type} of these arms: the choice types an option listing selects (`robot.type`, ...)."""
    return {r.prefix: r.type for r in roles}
