import pytest

from lerobot_gui.adapters.commands import (
    ARM_CHECK_COMMANDS,
    COMMANDS,
    calibration_prompt,
    captured_image_device,
    failure_text,
    find_port_phase,
    find_port_result,
    found_port,
    noted_at_start,
    output_dir,
    output_state,
)


def test_command_table():
    assert COMMANDS["lerobot-train"] is False
    assert all(COMMANDS[c] for c in ARM_CHECK_COMMANDS)


def test_find_port_result():
    out = "Remove the USB cable...\nThe port of this MotorsBus is '/dev/ttyACM1'\nReconnect the USB cable.\n"
    assert find_port_result(out, {"/dev/ttyACM1": "/dev/serial/by-id/x"}) == {
        "tty": "/dev/ttyACM1",
        "by_id": "/dev/serial/by-id/x",
    }
    assert find_port_result(out, {}) == {"tty": "/dev/ttyACM1", "by_id": None}
    assert find_port_result("OSError: Could not detect the port.", {}) is None


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("opencv__dev_video0", ("opencv", "/dev/video0")),
        ("opencv_0", ("opencv", "0")),
        ("realsense_1234", ("realsense", "1234")),
        ("something", (None, "something")),
    ],
)
def test_captured_image_device(stem, expected):
    assert captured_image_device(stem) == expected


MISMATCH = "INFO 12:00:00 Mismatch between calibration values in the motor and the calibration file\n"


def ask(arm_id: str) -> str:
    return (
        f"Press ENTER to use provided calibration file associated with the id {arm_id}, or type 'c' and press "
        "ENTER to run calibration: "
    )


TELEOP = [
    "--robot.port=/dev/ttyACM0",
    "--robot.id=alice_follower",
    "--teleop.port=/dev/ttyACM1",
    "--teleop.id=alice_leader",
]


def test_calibration_prompt_on_a_mismatch_warns_outside_calibrate():
    p = calibration_prompt(MISMATCH + ask("alice_leader"), "lerobot-teleoperate", TELEOP)
    assert p is not None
    assert (p["role"], p["id"], p["port"], p["mismatch"]) == ("leader", "alice_leader", "/dev/ttyACM1", True)
    assert "the ports are swapped" in p["warning"] and "`ttyACM1`" in p["warning"]
    p = calibration_prompt(MISMATCH + ask("alice_leader"), "lerobot-calibrate", TELEOP[2:])
    assert p is not None and p["role"] == "leader" and p["warning"] is None


def test_calibration_prompt_arm_is_found_by_its_id():
    p = calibration_prompt(MISMATCH + ask("alice_follower"), "lerobot-teleoperate", TELEOP)
    assert p is not None and (p["role"], p["port"]) == ("follower", "/dev/ttyACM0")
    # the log format doesn't matter: no file names are read
    p = calibration_prompt("so_leader.py:1 " + MISMATCH + ask("alice_follower"), "lerobot-teleoperate", TELEOP)
    assert p is not None and p["role"] == "follower"


def test_calibration_prompt_of_the_only_arm():
    # lerobot-calibrate passes one arm; without --robot.id lerobot names it itself
    p = calibration_prompt(ask("None"), "lerobot-calibrate", ["--robot.port=/dev/ttyACM0"])
    assert p is not None and (p["role"], p["port"], p["mismatch"]) == ("follower", "/dev/ttyACM0", False)


def test_calibration_prompt_with_the_same_id_on_both_arms():
    same = [a.replace("alice_leader", "alice_follower") for a in TELEOP]
    p = calibration_prompt(MISMATCH + ask("alice_follower"), "lerobot-teleoperate", same)
    assert p is not None and (p["role"], p["port"]) == (None, "")
    assert "the arm that asks" in p["warning"]


def test_calibration_prompt_mismatch_is_the_asking_arms():
    # the leader's mismatch, answered, then the follower asks without one
    out = MISMATCH + ask("alice_leader") + "\nINFO Writing calibration file associated with the id alice_leader\n"
    p = calibration_prompt(out + ask("alice_follower"), "lerobot-teleoperate", TELEOP)
    assert p is not None and (p["role"], p["mismatch"], p["warning"]) == ("follower", False, None)


def test_calibration_prompt_answered():
    out = MISMATCH + ask("alice_leader")
    assert calibration_prompt(out + "\nWriting calibration file", "lerobot-teleoperate", TELEOP) is None
    assert calibration_prompt(out + "\nRunning calibration of alice_leader", "lerobot-teleoperate", TELEOP) is None
    assert calibration_prompt("nothing", "lerobot-teleoperate", TELEOP) is None


def test_find_port_phase():
    assert find_port_phase("Finding all available ports") == "scan"
    assert find_port_phase("Remove the USB cable from your MotorsBus and press Enter when done.") == "unplug"
    assert find_port_phase("Remove the USB cable\nThe port of this MotorsBus is '/dev/ttyACM1'") == "reported"


def test_failure_text():
    assert failure_text(
        "lerobot-find-port", "OSError: Could not detect the port. No difference was found ([]).", 1
    ).startswith("No port disappeared")
    assert failure_text("lerobot-find-port", "More than one port was found", 1).startswith("More than one port")
    assert failure_text("lerobot-record", "a\nboom: bad thing\n\n", 1) == "boom: bad thing"
    assert failure_text("lerobot-record", "", 3) == "exit 3"


def test_what_a_run_is_read_with_depends_on_the_command():
    ports = [{"tty": "/dev/ttyACM0", "board": "/dev/serial/by-id/a"}, {"tty": "/dev/ttyUSB0", "board": None}]
    asked = []

    def listed():
        asked.append(1)
        return ports

    # find-port: the boards on the ports as it starts, to name the one it reports
    assert noted_at_start("lerobot-find-port", listed) == {"/dev/ttyACM0": "/dev/serial/by-id/a"}
    assert noted_at_start("lerobot-train", listed) == {} and len(asked) == 1  # the others don't list them
    out = "Remove the USB cable\nThe port of this MotorsBus is '/dev/ttyACM0'"
    assert found_port("lerobot-find-port", out, {"/dev/ttyACM0": "/dev/serial/by-id/a"}) == {
        "tty": "/dev/ttyACM0",
        "by_id": "/dev/serial/by-id/a",
    }
    assert found_port("lerobot-teleoperate", out, {}) is None
    assert output_state("lerobot-find-port", [], out, True) == {"prompt": None, "phase": "reported"}
    asking = MISMATCH + ask("alice_leader")
    assert output_state("lerobot-teleoperate", TELEOP, asking, True)["prompt"] is not None
    assert output_state("lerobot-teleoperate", TELEOP, asking, False) == {"prompt": None, "phase": None}  # ended
    # train: where it writes, when given
    assert output_dir("lerobot-train", ["--steps=10", "--output_dir=/data/runs/act"]) == "/data/runs/act"
    assert (
        output_dir("lerobot-train", ["--output_dir="]) is None
        and output_dir("lerobot-record", ["--output_dir=x"]) is None
    )
