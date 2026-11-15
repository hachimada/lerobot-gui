"""The arms' roles: every place that names an arm reads its flags, type and folders from one definition."""

from __future__ import annotations

import pytest

from lerobot_gui.adapters.arms import calibration_file
from lerobot_gui.adapters.commands import calibration_prompt
from lerobot_gui.adapters.roles import CAMERAS_FLAG, FOLLOWER, LEADER, ROLES, other, role, types
from lerobot_gui.commands import hardware
from lerobot_gui.commands.extras import HW_FLAGS

from .commands_helpers import build, flags


def test_the_two_arms():
    assert [r.name for r in ROLES] == ["follower", "leader"]
    assert role("leader") is LEADER and other(LEADER) is FOLLOWER and other(FOLLOWER) is LEADER
    with pytest.raises(ValueError, match="No arm role"):
        role("gripper")
    # the Hardware page's stored values (saved in the browser: their names must not change)
    assert [(r.port_key, r.id_key, r.board_key) for r in ROLES] == [
        ("followerPort", "followerId", "followerBoard"),
        ("leaderPort", "leaderId", "leaderBoard"),
    ]
    assert types(FOLLOWER, LEADER) == {"robot": "so101_follower", "teleop": "so101_leader"}
    assert FOLLOWER.type in FOLLOWER.checked_types and LEADER.type in LEADER.checked_types


def test_the_flags_the_hardware_page_writes():
    expected = {"robot.type", "robot.port", "robot.id", "robot.cameras", "teleop.type", "teleop.port", "teleop.id"}
    assert expected == HW_FLAGS
    assert CAMERAS_FLAG == "robot.cameras"


def test_each_arm_is_written_with_its_own_flags(settings):
    args, _ = build(settings, "teleoperate")
    f = flags(args)
    for r in ROLES:
        assert f[r.flag("type")] == r.type
    assert (f["robot.port"], f["teleop.port"]) == ("/dev/ttyACM0", "/dev/ttyACM1")


def test_calibrate_lists_and_writes_only_the_arm_calibrated(settings):
    for r in ROLES:
        args, _ = build(settings, "calibrate", {"gui.target": r.name})
        assert {k.split(".")[0] for k in flags(args)} == {r.prefix}


def test_the_hardware_page_has_a_group_per_arm(settings):
    from .commands_helpers import context

    groups = hardware.form(context(settings, ""))["groups"]
    assert [g["title"] for g in groups] == [r.label for r in ROLES]
    assert [f["key"] for g in groups for f in g["fields"]] == ["followerPort", "followerId", "leaderPort", "leaderId"]


def test_calibration_file_and_prompt_name_the_arm(tmp_path):
    folders = {"robots": tmp_path / "robots", "teleoperators": tmp_path / "teleoperators"}
    assert calibration_file(folders, "leader", "alice") == tmp_path / "teleoperators" / "so_leader" / "alice.json"
    output = "Press ENTER to use provided calibration file associated with the id alice, or type 'c'"
    prompt = calibration_prompt(output, "lerobot-teleoperate", ["--robot.id=bob", "--teleop.id=alice"])
    assert prompt is not None and prompt["role"] == "leader"
