"""What the GUI knows about the command-line tools it runs: lerobot's, and Trackio's dashboard."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Literal

from .roles import ROLES

#: allowlisted commands -> whether they use the robot or the cameras (one such job at a time)
COMMANDS: dict[str, bool] = {
    "lerobot-find-port": True,
    "lerobot-find-cameras": True,
    "lerobot-calibrate": True,
    "lerobot-teleoperate": True,
    "lerobot-record": True,
    "lerobot-rollout": True,
    "lerobot-train": False,
    # the one that isn't lerobot's: `trackio show`, the dashboard of the runs Train logs with Trackio
    "trackio": False,
}

#: lerobot's commands: they read and write lerobot's data (datasets, calibration files, the Hub caches)
LEROBOT_COMMANDS = frozenset(c for c in COMMANDS if c.startswith("lerobot-"))

#: commands that drive the follower: checked for swapped arms before they start
ARM_CHECK_COMMANDS = frozenset({"lerobot-teleoperate", "lerobot-record", "lerobot-rollout"})

_FIND_PORT = re.compile(r"The port of this MotorsBus is '([^']+)'")
_CAPTURE = re.compile(r"^(opencv|realsense)_(.+)$")
CAPTURE_SUFFIXES = (".png", ".jpg", ".jpeg")


# ----------------------------------------------- what a run is read with
# The job runner calls these for every command; what each command needs is decided here.


def noted_at_start(command: str, ports: Callable[[], list[dict]]) -> dict[str, str]:
    """What a command's output is read against, noted as it starts. lerobot-find-port reports the port
    from before the unplug: the boards on the ports then (tty -> board)."""
    if command == "lerobot-find-port":
        return {p["tty"]: p["board"] for p in ports() if p["board"]}
    return {}


def output_state(command: str, args: list[str], tail: str, running: bool) -> dict:
    """What the output says now: lerobot's calibration prompt (while it runs), where lerobot-find-port is."""
    return {
        "prompt": calibration_prompt(tail, command, args) if running else None,
        "phase": find_port_phase(tail) if command == "lerobot-find-port" else None,
    }


def found_port(command: str, output: str, noted: dict[str, str]) -> dict | None:
    """The port lerobot-find-port reported, with its board (None for another command, or before it says)."""
    return find_port_result(output, noted) if command == "lerobot-find-port" else None


def output_dir(command: str, args: list[str]) -> str | None:
    """Where a training run writes (lerobot-train's `--output_dir`, when it is given)."""
    if command != "lerobot-train":
        return None
    return next((a.split("=", 1)[1] for a in args if a.startswith("--output_dir=")), None) or None


def find_port_result(output: str, snapshot: dict[str, str]) -> dict | None:
    """The port lerobot-find-port reported, mapped to its /dev/serial/by-id link.

    The reported name is the one from before the unplug, so `snapshot`
    (tty -> by-id link) must be taken when the command starts.
    """
    m = _FIND_PORT.search(output)
    if not m:
        return None
    tty = m.group(1)
    return {"tty": tty, "by_id": snapshot.get(os.path.realpath(tty)) or snapshot.get(tty)}


def captured_image_device(stem: str) -> tuple[str | None, str]:
    """(camera type, device) from a lerobot-find-cameras file name.

    It saves `<type>_<id with "/" replaced by "_">.png`, e.g. `opencv__dev_video0.png`.
    """
    m = _CAPTURE.match(stem)
    ident = m.group(2) if m else stem
    device = "/dev/" + ident[len("_dev_") :] if ident.startswith("_dev_") else ident
    return (m.group(1) if m else None), device


CALIB_PROMPT = "Press ENTER to use provided calibration file"
_CALIB_DONE = re.compile(r"Writing calibration file|Running calibration|to the middle of their range")
_CALIB_ID = re.compile(r"with the id (.+?),")
_CALIB_MISMATCH = "Mismatch between calibration values"
#: the arms a command passes, by the prefix of their flags
_ARM_FLAGS = tuple((r.name, f"--{r.prefix}.") for r in ROLES)


def _flag(args: list[str], flag: str) -> str | None:
    return next((a[len(flag) :] for a in args if a.startswith(flag)), None)


def calibration_prompt(output: str, command: str, args: list[str]) -> dict | None:
    """lerobot waits at its "use the calibration file?" prompt: which arm, and was it a mismatch.

    The arm is the one of the command whose `--robot.id` / `--teleop.id` is the id in the prompt (or
    the only arm the command passes). Enter writes the file into the motors on that port, which is
    wrong when the ports are swapped, so a mismatch outside lerobot-calibrate comes with a warning.
    """
    p = output.rfind(CALIB_PROMPT)
    if p < 0:
        return None
    after = output[p + len(CALIB_PROMPT) :]
    if _CALIB_DONE.search(after):
        return None
    m = _CALIB_ID.search(after)
    arm_id = m.group(1) if m else ""
    arms = [(role, prefix) for role, prefix in _ARM_FLAGS if any(a.startswith(prefix) for a in args)]
    by_id = [(role, prefix) for role, prefix in arms if _flag(args, f"{prefix}id=") == arm_id]
    # both arms with the same id: which one asks isn't known
    found = by_id if len(by_id) == 1 else arms if len(arms) == 1 else []
    role, prefix = found[0] if found else (None, None)
    port = (_flag(args, f"{prefix}port=") or "") if prefix else ""
    # what lerobot printed since the previous prompt (each arm connects and asks in turn)
    previous = output.rfind(CALIB_PROMPT, 0, p)
    mismatch = _CALIB_MISMATCH in output[max(previous + 1, p - 2000, 0) : p]
    prompt = {"role": role, "id": arm_id, "port": port, "mismatch": mismatch, "warning": None}
    if mismatch and command != "lerobot-calibrate":
        arm = f"the {role}'s motors on `{os.path.basename(port)}`" if role else "the motors of the arm that asks"
        prompt["warning"] = (
            f"lerobot says {arm} don't hold the `{arm_id}` calibration. On an arm that worked before, this means "
            "the ports are swapped: press Stop and check them with Find port on the Hardware page. Enter writes "
            f"`{arm_id}.json` into those motors, which is right only if it really is that arm (e.g. to restore it "
            "after a swapped run)."
        )
    return prompt


def find_port_phase(output: str) -> Literal["scan", "unplug", "reported"]:
    """Where lerobot-find-port is: "scan" (reading the ports), "unplug" (waiting for Enter) or "reported"."""
    if _FIND_PORT.search(output):
        return "reported"
    return "unplug" if "Remove the USB cable" in output else "scan"


def failure_text(command: str, output: str, returncode: int | None) -> str:
    """Why a command failed, in a line: lerobot-find-port's errors explained, else the last output line."""
    if command == "lerobot-find-port":
        if "No difference was found" in output:
            return (
                "No port disappeared when you clicked Enter. Unplug one arm's USB after it asks, then click Enter "
                "while it is still unplugged."
            )
        if "More than one port was found" in output:
            return "More than one port disappeared. Unplug the USB of only one arm."
    lines = [line for line in output.strip().splitlines() if line.strip()]
    return (lines[-1] if lines else f"exit {returncode}")[:300]
