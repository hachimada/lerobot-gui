import pytest

from lerobot_gui.adapters.arms import arms_from_args, check_arms

from .conftest import FOLLOWER_CAL, LEADER_CAL, calibration_folders

FIELDS = ("homing_offset", "range_min", "range_max")


def motors(cal):
    return {name: {k: c[k] for k in FIELDS} for name, c in cal.items()}


def reader(by_port):
    def read(port, motor_ids):
        value = by_port[port]
        if isinstance(value, Exception):
            raise value
        assert set(motor_ids) == set(FOLLOWER_CAL)  # motor names/ids come from the calibration file
        return value

    return read


def arms(follower_port="/dev/ttyACM0", leader_port="/dev/ttyACM1"):
    return [
        {"role": "follower", "port": follower_port, "id": "my_follower_arm"},
        {"role": "leader", "port": leader_port, "id": "my_leader_arm"},
    ]


def folders(hf_home):
    """the calibration folders of the fake workspace's lerobot"""
    return calibration_folders(hf_home / "calibration")


def by_role(result):
    return {a["role"]: a for a in result["arms"]}


def test_each_arm_holds_its_own_calibration(workspace):
    _, hf_home = workspace
    result = check_arms(
        arms(),
        folders(hf_home),
        read=reader({"/dev/ttyACM0": motors(FOLLOWER_CAL), "/dev/ttyACM1": motors(LEADER_CAL)}),
    )
    assert result["swapped"] is False
    assert {r: a["status"] for r, a in by_role(result).items()} == {"follower": "ok", "leader": "ok"}


def test_swapped_ports_are_detected(workspace):
    _, hf_home = workspace
    result = check_arms(
        arms(),
        folders(hf_home),
        read=reader({"/dev/ttyACM0": motors(LEADER_CAL), "/dev/ttyACM1": motors(FOLLOWER_CAL)}),
    )
    assert result["swapped"] is True
    follower, leader = by_role(result)["follower"], by_role(result)["leader"]
    assert (follower["status"], follower["other_role"], follower["other_id"]) == ("other", "leader", "my_leader_arm")
    assert (leader["status"], leader["other_role"]) == ("other", "follower")


def test_motors_matching_no_file(workspace):
    _, hf_home = workspace
    odd = motors(FOLLOWER_CAL)
    odd["gripper"] = {**odd["gripper"], "range_max": 1}
    result = check_arms(arms()[:1], folders(hf_home), read=reader({"/dev/ttyACM0": odd}))
    assert by_role(result)["follower"]["status"] == "mismatch"
    assert result["swapped"] is False


def test_unreadable_port(workspace):
    _, hf_home = workspace
    result = check_arms(
        arms()[:1], folders(hf_home), read=reader({"/dev/ttyACM0": ConnectionError("no status packet")})
    )
    a = by_role(result)["follower"]
    assert a["status"] == "error" and "no status packet" in a["detail"]


def test_missing_calibration_file(workspace):
    _, hf_home = workspace
    missing = [{"role": "follower", "port": "/dev/ttyACM0", "id": "typo_arm"}]
    result = check_arms(missing, folders(hf_home), read=reader({"/dev/ttyACM0": motors(LEADER_CAL)}))
    # the motors still identify the arm on that port: it is the leader
    assert by_role(result)["follower"]["status"] == "other"


def test_custom_calibration_dir(workspace, tmp_path):
    _, hf_home = workspace
    d = tmp_path / "cal"
    d.mkdir()
    (d / "my_follower_arm.json").write_text(
        (hf_home / "calibration/robots/so_follower/my_follower_arm.json").read_text()
    )
    arm = [{"role": "follower", "port": "/dev/ttyACM0", "id": "my_follower_arm", "calibration_dir": str(d)}]
    assert (
        check_arms(arm, folders(hf_home), read=reader({"/dev/ttyACM0": motors(FOLLOWER_CAL)}))["arms"][0]["status"]
        == "ok"
    )


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (
            [
                "--robot.type=so101_follower",
                "--robot.port=/dev/ttyACM0",
                "--robot.id=f",
                "--teleop.type=so101_leader",
                "--teleop.port=/dev/ttyACM1",
                "--teleop.id=l",
            ],
            [("follower", "/dev/ttyACM0", "f"), ("leader", "/dev/ttyACM1", "l")],
        ),
        (
            ["--robot.type=so100_follower", "--robot.port=/dev/ttyACM0", "--robot.id=f"],
            [("follower", "/dev/ttyACM0", "f")],
        ),
        (
            ["--robot.type=koch_follower", "--robot.port=/dev/ttyACM0", "--robot.id=f"],
            [],
        ),  # only SO-100/101 are checked
        (["--robot.type=so101_follower", "--robot.id=f"], []),  # no port
    ],
)
def test_arms_from_args(args, expected):
    assert [(a["role"], a["port"], a["id"]) for a in arms_from_args(args)] == expected


def test_calibration_folders_lerobot_reports(workspace, tmp_path):
    # HF_LEROBOT_CALIBRATION elsewhere: the files are there, not under HF_LEROBOT_HOME
    _, hf_home = workspace
    elsewhere = calibration_folders(tmp_path / "calibration-elsewhere")
    (elsewhere["robots"] / "so_follower").mkdir(parents=True)
    (elsewhere["robots"] / "so_follower" / "my_follower_arm.json").write_text(
        (hf_home / "calibration/robots/so_follower/my_follower_arm.json").read_text()
    )
    arm = [{"role": "follower", "port": "/dev/ttyACM0", "id": "my_follower_arm"}]
    result = check_arms(arm, elsewhere, read=reader({"/dev/ttyACM0": motors(FOLLOWER_CAL)}))["arms"][0]
    assert result["status"] == "ok"
    assert result["file"] == str(elsewhere["robots"] / "so_follower" / "my_follower_arm.json")
