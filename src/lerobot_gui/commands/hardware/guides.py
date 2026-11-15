"""What a Check arms result means and what to do about it, and the error when Run was refused."""

from __future__ import annotations

from ... import schemas
from ...schemas import SetAction
from ..context import Context, basename
from ..model import Action, check_arms, go, scroll, set_values
from .ports import swap_ports

ARM_EXPLAIN = (
    "Reads the zero point and limits stored in each arm's motors over USB (nothing moves) and compares them "
    "with the calibration files. After normal use each arm's motors hold its own file, so this tells which arm "
    "is really on each port before anything moves."
)


def restore(name: str) -> SetAction:
    """Calibrate the arm: Enter writes its own file back into its motors."""
    return set_values("calibrate", {"gui.target": name}, f"Calibrate the {name}", go="calibrate")


def arm_guide(ctx: Context, arm: schemas.ArmResult, result: schemas.ArmCheck) -> schemas.ArmGuide:
    """What a Check arms result means and what to do about it."""
    crossed = sum(a["status"] == "other" for a in result["arms"]) == 2
    find_port = scroll("findport-card", "Go to Find port")
    again = check_arms("Check again")
    role, port = arm["role"], f"`{basename(arm['port'])}`"
    status = arm["status"]
    if status == "ok":
        return {
            "level": "ok",
            "title": "OK",
            "text": f"Its motors hold the `{arm['id']}` calibration: {port} is the {role}.",
        }
    if status == "other":
        return {
            "level": "err",
            "title": "NG: another arm's calibration",
            "text": f"Its motors hold the {arm.get('detail')} calibration, not `{arm['id']}`. Either the ports are "
            "swapped, or an earlier run with swapped ports wrote that file into this arm.",
            "steps": [
                f"Find port: unplug this arm's USB when asked. If it reports another port than {port}, the ports "
                f"are wrong: assign the right one{', or swap the two' if crossed else ''}.",
                "If the port is right: power-cycle this arm and Check again. A wrong write that wasn't saved goes away.",
                f"Still NG: Calibrate the {role} and press Enter. That writes `{arm['id']}.json` back into its motors.",
            ],
            "actions": [*([swap_ports(ctx, "Swap the two ports")] if crossed else []), find_port, again, restore(role)],
        }
    if status == "mismatch":
        return {
            "level": "warn",
            "title": "Matches no file",
            "text": f"Its motors match no calibration file: new or replaced motors, or this arm was never calibrated "
            f"as `{arm['id']}`. lerobot will ask whether to write the file when it connects.",
            "steps": [
                f"Make sure {port} really is the {role} (Find port).",
                f"Then Calibrate the {role}: Enter writes `{arm['id']}.json` into the motors, `c` calibrates from "
                "scratch.",
            ],
            "actions": [find_port, restore(role)],
        }
    if status == "no_file":
        return {
            "level": "warn",
            "title": "No calibration file",
            "text": f"There is no `{arm['id']}.json` to compare with.",
            "steps": [
                "Check the id for typos (the existing files are listed on the right).",
                f"Or create it: Calibrate the {role} runs a full calibration.",
            ],
            "actions": [restore(role)],
        }
    return {
        "level": "err",
        "title": "Could not read",
        "text": arm.get("detail") or status,
        "steps": [
            "Is the arm powered, and its USB plugged in?",
            "Close anything else using the port (another GUI, a terminal running lerobot).",
            "A motor in an overload error: power-cycle the arm.",
        ],
        "actions": [again],
    }


def with_guides(ctx: Context, result: schemas.ArmCheck) -> schemas.ArmCheck:
    """A Check arms result (as the page sent it back) with what each arm's result means."""
    arms: list[schemas.ArmResult] = [{**a, "guide": arm_guide(ctx, a, result)} for a in result["arms"]]
    return {**result, "arms": arms}


def preflight_message(ctx: Context, preflight: schemas.ArmCheck) -> schemas.Message:
    """The error shown when Run was refused because the arms look swapped."""
    bad = [a for a in preflight["arms"] if a["status"] == "other"]
    crossed = len(bad) == 2 and all(a.get("other_role") not in (None, "", a["role"]) for a in bad)
    actions: list[Action] = []
    if crossed:
        actions.append(swap_ports(ctx, "Swap the follower and leader ports"))
    actions += [
        go("hardware", "Find port (Hardware)"),
        go("calibrate", "Restore with Calibrate"),
        {
            "type": "run_force",
            "label": "Run anyway",
            "confirm": "Run anyway?\n\nIf the ports are swapped, the leader arm is driven as the follower.",
        },
    ]
    what = "; ".join(
        f"the {a['role']} port `{basename(a['port'])}` has motors holding the {a.get('detail')} calibration"
        for a in bad
    )
    advice = (
        "Both arms point at each other: the ports are swapped."
        if crossed
        else "Check which arm is on which port with Find port on the Hardware page; if the ports are right, restore "
        "the arm with Calibrate → Enter."
    )
    return {
        "level": "err",
        "text": f"Not started: {what}. Either the ports are swapped (the leader would be driven as the follower), or "
        f"an earlier run with swapped ports wrote that calibration into the arm. {advice}",
        "actions": actions,
    }
