"""The Hardware page: which port, calibration id and cameras every command uses, and their checks.

Ports and cameras are named as lerobot-find-port and lerobot-find-cameras report them (`/dev/ttyACM0`,
`/dev/tty.usbmodem…`, `COM3`; `/dev/video0`, `0`). A port can be renumbered by replugging, so each
arm's assignment also remembers its USB-serial board (devices.ports): a later mismatch is flagged
with a one-click fix. Cameras aren't followed (nothing tells them apart on every OS): the cameras
are the ones in the last frames lerobot-find-cameras saved.

    page.py    the values, and the fields of each arm's port and calibration id
    ports.py   what a port choice stores (the board on it), assigning, swapping, following a renumbering
    checks.py  the checks, said on the command pages and in the Hardware page's Setup status
    guides.py  what a Check arms result means and what to do
    view.py    what the Hardware page shows besides its fields
"""

from .checks import hw_checks, setup_status, summary
from .guides import arm_guide, preflight_message
from .page import PAGE, values
from .ports import arms_to_check, assign, follow_patch, remember_checked
from .view import form, view

__all__ = [
    "PAGE",
    "arm_guide",
    "arms_to_check",
    "assign",
    "follow_patch",
    "form",
    "hw_checks",
    "preflight_message",
    "remember_checked",
    "setup_status",
    "summary",
    "values",
    "view",
]
