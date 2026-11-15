"""Tell which physical arm is on a port: compare the calibration stored in its motors with the
calibration files. Read-only: opens the port, reads the registers, closes it (no torque, no writes).

lerobot writes the calibration file into the motors whenever you press Enter at its
"Press ENTER to use provided calibration file" prompt, so after a normal run each arm's motors
hold exactly its own file. If the follower port's motors hold the *leader* file, the ports are
swapped and the leader would be driven as the follower.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .roles import ROLES, role

FIELDS = ("homing_offset", "range_min", "range_max")


def calibration_file(folders: dict[str, Path], name: str, arm_id: str, calibration_dir: str | None = None) -> Path:
    """Where lerobot keeps an arm's calibration: `--*.calibration_dir` when given, else in its folders."""
    if calibration_dir:
        return Path(calibration_dir) / f"{arm_id}.json"
    r = role(name)
    return folders[r.calibration_kind] / r.calibration_class / f"{arm_id}.json"


def read_motor_calibration(port: str, motor_ids: dict[str, int]) -> dict[str, dict[str, int]]:
    from lerobot.motors import Motor, MotorNormMode, SerialMotorsBus

    motors = {name: Motor(mid, "sts3215", MotorNormMode.RANGE_M100_100) for name, mid in motor_ids.items()}
    bus = SerialMotorsBus(port=port, motors=motors)
    bus.connect(handshake=True)
    try:
        cal = bus.read_calibration()
    finally:
        bus.disconnect(disable_torque=False)
    return {m: {k: int(getattr(c, k)) for k in FIELDS} for m, c in cal.items()}


def _load(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _matches(motor_cal: dict, file_cal: dict) -> bool:
    return bool(file_cal) and all(
        name in motor_cal and all(motor_cal[name][k] == file_cal[name].get(k) for k in FIELDS) for name in file_cal
    )


MotorReader = Callable[[str, dict[str, int]], dict[str, dict[str, int]]]


def check_arms(arms: list[dict], folders: dict[str, Path], read: MotorReader | None = None) -> dict:
    """arms: [{"role": "follower"|"leader", "port": str, "id": str, "calibration_dir": str|None}];
    folders: lerobot's calibration folders (`Settings.calibration`).

    Each result has a status:
      ok        the motors hold this arm's calibration file
      other     the motors hold another arm's file (detail names it): the port belongs to that arm
      mismatch  the motors match no calibration file (new motors, or never written)
      no_file   this arm's calibration file doesn't exist (lerobot will calibrate)
      error     the port couldn't be read (unplugged, powered off, motor error)
    """
    candidates: dict[str, dict] = {}
    for r in ROLES:
        for p in sorted((folders[r.calibration_kind] / r.calibration_class).glob("*.json")):
            if (data := _load(p)) is not None:
                candidates[f"{r.name}:{p.stem}"] = data
    results = []
    for arm in arms:
        own_path = calibration_file(folders, arm["role"], arm["id"], arm.get("calibration_dir"))
        res = {
            "role": arm["role"],
            "port": arm["port"],
            "id": arm["id"],
            "file": str(own_path),
            "status": "",
            "detail": "",
        }
        own = _load(own_path)
        if own is not None:
            candidates.setdefault(f"{arm['role']}:{arm['id']}", own)
        reference = own or next(iter(candidates.values()), None)
        if reference is None:
            res.update(status="no_file", detail="No calibration file to compare with.")
            results.append(res)
            continue
        try:
            motor_cal = (read or read_motor_calibration)(arm["port"], {name: c["id"] for name, c in reference.items()})
        except Exception as exc:
            res.update(status="error", detail=f"{type(exc).__name__}: {exc}"[:300])
            results.append(res)
            continue
        if own is not None and _matches(motor_cal, own):
            res["status"] = "ok"
        else:
            hit = next(
                (
                    key
                    for key, data in candidates.items()
                    if key != f"{arm['role']}:{arm['id']}" and _matches(motor_cal, data)
                ),
                None,
            )
            if hit:
                other_role, arm_id = hit.split(":", 1)
                res.update(status="other", detail=f"{other_role} {arm_id}", other_role=other_role, other_id=arm_id)
            else:
                res.update(status="no_file" if own is None else "mismatch")
        results.append(res)
    return {"arms": results, "swapped": any(r["status"] == "other" for r in results)}


def arms_from_args(args: list[str]) -> list[dict]:
    """The follower/leader (port, id, calibration_dir) of a lerobot command line (SO-100/101 only)."""
    flags = {}
    for a in args:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            flags[k] = v
    arms = []
    for r in ROLES:
        port, arm_id = flags.get(r.flag("port")), flags.get(r.flag("id"))
        if flags.get(r.flag("type")) in r.checked_types and port and arm_id:
            arms.append(
                {"role": r.name, "port": port, "id": arm_id, "calibration_dir": flags.get(r.flag("calibration_dir"))}
            )
    return arms


ARM_STATUS = {
    "ok": "motors hold this arm's calibration",
    "other": "motors hold another arm's calibration",
    "mismatch": "motors match no calibration file (lerobot will ask to write it)",
    "no_file": "no calibration file (lerobot will calibrate)",
    "error": "could not read the motors",
}


def arm_line(arm: Mapping[str, Any]) -> str:
    """One line about an arm's check result, e.g. for the job output card."""
    detail = f" ({arm['detail']})" if arm.get("detail") else ""
    return f"Arm check, {arm['role']}: {ARM_STATUS.get(arm['status'], arm['status'])}{detail}."
