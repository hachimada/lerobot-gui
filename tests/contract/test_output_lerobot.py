"""lerobot's output, as the GUI reads it: lerobot's own code runs here on fake devices.

The GUI reads what lerobot-find-port prints, the calibration prompt of the arms and the file names
of lerobot-find-cameras. These tests run that code of the installed lerobot with its devices
replaced (no serial port or camera is opened) and check the GUI still understands the output.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

pytest.importorskip("lerobot")
pytestmark = pytest.mark.lerobot

from lerobot_gui import workspace  # noqa: E402
from lerobot_gui.adapters.commands import (  # noqa: E402
    calibration_prompt,
    captured_image_device,
    failure_text,
    find_port_phase,
    find_port_result,
)

# ------------------------------------------------------------------ find-port


@pytest.fixture
def find_port(monkeypatch):
    """lerobot-find-port with the given port scans (before and after the unplug) and Enter answered."""
    module = importlib.import_module("lerobot.scripts.lerobot_find_port")
    monkeypatch.setattr(module.time, "sleep", lambda s: None)

    def run(capsys, before: list[str], after: list[str]) -> tuple[str, list[str]]:
        scans = iter([before, after])
        out: list[str] = []
        phases: list[str] = []

        def scan() -> list[str]:
            out.append(capsys.readouterr().out)
            phases.append(find_port_phase("".join(out)))
            return next(scans)

        def enter(prompt: str = "") -> str:
            out.append(capsys.readouterr().out + prompt)
            phases.append(find_port_phase("".join(out)))
            return ""

        monkeypatch.setattr(module, "find_available_ports", scan)
        monkeypatch.setattr("builtins.input", enter)
        try:
            module.find_port()
        finally:
            out.append(capsys.readouterr().out)
        return "".join(out), phases

    return run


def test_find_port_output(find_port, capsys):
    out, phases = find_port(capsys, ["/dev/ttyACM0", "/dev/ttyACM1"], ["/dev/ttyACM0"])
    # scanning, then waiting for Enter (unplugged), then scanning again
    assert phases == ["scan", "unplug", "unplug"]
    assert find_port_phase(out) == "reported"
    assert find_port_result(out, {"/dev/ttyACM1": "/dev/serial/by-id/usb-arm"}) == {
        "tty": "/dev/ttyACM1",
        "by_id": "/dev/serial/by-id/usb-arm",
    }


@pytest.mark.parametrize(
    ("after", "explained"),
    [
        (["/dev/ttyACM0", "/dev/ttyACM1"], "No port disappeared"),
        ([], "More than one port disappeared"),
    ],
)
def test_find_port_errors_are_explained(find_port, capsys, after, explained):
    with pytest.raises(OSError) as error:
        find_port(capsys, ["/dev/ttyACM0", "/dev/ttyACM1"], after)
    output = f"Traceback (most recent call last):\n  ...\nOSError: {error.value}\n"
    assert failure_text("lerobot-find-port", output, 1).startswith(explained)
    assert find_port_result(output, {}) is None


# ---------------------------------------------------------------- calibration

TELEOP = [
    "--robot.type=so101_follower",
    "--robot.port=/nonexistent/ttyACM0",
    "--robot.id=alice_follower",
    "--teleop.type=so101_leader",
    "--teleop.port=/nonexistent/ttyACM1",
    "--teleop.id=alice_leader",
]


class _Transcript(logging.Handler):
    """What the command prints: lerobot's log lines and the prompts of input()."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.parts: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.parts.append(f"INFO {record.filename}:{record.lineno} {record.getMessage()}\n")

    @property
    def text(self) -> str:
        return "".join(self.parts)


class _Stop(Exception):
    pass


def _arm(role: str, arm_id: str, port: str, calibration_dir: Path) -> Any:
    """An SO-101 arm as lerobot makes it, with a calibration file and a fake motor bus."""
    from lerobot.motors import MotorCalibration
    from lerobot.robots import make_robot_from_config
    from lerobot.robots.so_follower import SOFollowerRobotConfig
    from lerobot.teleoperators import make_teleoperator_from_config
    from lerobot.teleoperators.so_leader import SOLeaderTeleopConfig

    def make() -> Any:  # the SO-101 classes, which have a motor bus
        if role == "follower":
            return make_robot_from_config(SOFollowerRobotConfig(port=port, id=arm_id, calibration_dir=calibration_dir))
        return make_teleoperator_from_config(
            SOLeaderTeleopConfig(port=port, id=arm_id, calibration_dir=calibration_dir)
        )

    arm = make()
    arm.calibration = {
        name: MotorCalibration(id=m.id, drive_mode=0, homing_offset=0, range_min=0, range_max=4095)
        for name, m in arm.bus.motors.items()
    }
    arm._save_calibration()
    arm = make()  # reads the file back, as a command does
    assert arm.calibration
    # the motors: not connected, and not holding that calibration
    arm.bus = MagicMock(is_connected=False, is_calibrated=False, motors=arm.bus.motors)
    return arm


@pytest.fixture
def transcript():
    handler = _Transcript()
    root = logging.getLogger()
    level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield handler
    root.removeHandler(handler)
    root.setLevel(level)


def _answering(monkeypatch, transcript: _Transcript, answers: list[str], seen: list):
    """input(): records the prompt and what the GUI makes of the output so far, then answers."""

    def answer(prompt: str = "") -> str:
        transcript.parts.append(prompt)
        seen.append(calibration_prompt(transcript.text, "lerobot-teleoperate", TELEOP))
        if not answers:
            raise _Stop
        return answers.pop(0)

    monkeypatch.setattr("builtins.input", answer)


@pytest.mark.parametrize(
    ("role", "arm_id", "port"),
    [("follower", "alice_follower", "/nonexistent/ttyACM0"), ("leader", "alice_leader", "/nonexistent/ttyACM1")],
)
def test_calibration_prompt_on_connect(tmp_path, monkeypatch, transcript, role, arm_id, port):
    arm = _arm(role, arm_id, port, tmp_path)
    seen: list = []
    _answering(monkeypatch, transcript, [""], seen)
    arm.connect()  # lerobot finds the mismatch and asks; Enter writes the file
    assert seen == [
        {"role": role, "id": arm_id, "port": port, "mismatch": True, "warning": seen[0]["warning"]},
    ]
    assert seen[0]["warning"] and "the ports are swapped" in seen[0]["warning"]
    arm.bus.write_calibration.assert_called_once()
    # answered: no prompt any more
    assert calibration_prompt(transcript.text, "lerobot-teleoperate", TELEOP) is None


def test_calibration_prompt_ends_when_calibration_runs(tmp_path, monkeypatch, transcript):
    from lerobot.motors import SerialMotorsBus

    arm = _arm("leader", "alice_leader", "/nonexistent/ttyACM1", tmp_path)
    # the calibration is recorded by lerobot's motor bus, which asks first
    bus = arm.bus
    bus._get_motors_list.side_effect = lambda motors=None: list(bus.motors)
    bus.record_calibration.side_effect = lambda *a, **kw: SerialMotorsBus.record_calibration(bus, *a, **kw)
    seen: list = []
    _answering(monkeypatch, transcript, ["c"], seen)
    with pytest.raises(_Stop):
        arm.connect()  # 'c': lerobot calibrates, then asks to move the arm (stopped there)
    assert seen[0] is not None and seen[0]["role"] == "leader"
    assert seen[1] is None


def test_calibration_prompt_of_each_arm_in_turn(tmp_path, monkeypatch, transcript):
    leader = _arm("leader", "alice_leader", "/nonexistent/ttyACM1", tmp_path / "leader")
    follower = _arm("follower", "alice_follower", "/nonexistent/ttyACM0", tmp_path / "follower")
    follower.bus.is_calibrated = True  # only the leader asks on connect
    seen: list = []
    _answering(monkeypatch, transcript, ["", ""], seen)
    leader.connect()
    follower.connect()
    follower.calibrate()  # as lerobot-calibrate asks: no mismatch
    assert [(p["role"], p["mismatch"]) for p in seen] == [("leader", True), ("follower", False)]


def test_calibration_prompt_of_lerobot_calibrate(tmp_path, monkeypatch, transcript):
    """lerobot-calibrate passes one arm and asks without a mismatch."""
    arm = _arm("follower", "alice_follower", "/nonexistent/ttyACM0", tmp_path)
    args = ["--robot.type=so101_follower", "--robot.port=/nonexistent/ttyACM0", "--robot.id=alice_follower"]
    seen: list = []

    def answer(prompt: str = "") -> str:
        transcript.parts.append(prompt)
        seen.append(calibration_prompt(transcript.text, "lerobot-calibrate", args))
        return ""

    monkeypatch.setattr("builtins.input", answer)
    arm.connect(calibrate=False)
    arm.calibrate()
    assert seen == [
        {"role": "follower", "id": "alice_follower", "port": "/nonexistent/ttyACM0", "mismatch": False, "warning": None}
    ]


def test_calibration_files_are_where_lerobot_keeps_them(tmp_path, monkeypatch):
    """The GUI's calibration folders (read from lerobot's constants) hold the files lerobot's arms use, for
    the type each role writes and the ones the arm check reads."""
    import lerobot.robots.robot as robot_module
    import lerobot.robots.so_follower  # registers the SO-100/101 followers
    import lerobot.teleoperators.so_leader  # noqa: F401  registers the SO-100/101 leaders
    import lerobot.teleoperators.teleoperator as teleop_module
    import lerobot.utils.constants as constants
    from lerobot.robots import RobotConfig, make_robot_from_config
    from lerobot.teleoperators import TeleoperatorConfig, make_teleoperator_from_config

    from lerobot_gui.adapters.arms import calibration_file
    from lerobot_gui.adapters.roles import FOLLOWER, LEADER
    from lerobot_gui.settings import default_calibration

    # HF_LEROBOT_CALIBRATION as lerobot read it from the environment, in a temp dir (an arm makes its folder)
    for module in (constants, robot_module, teleop_module):
        monkeypatch.setattr(module, "HF_LEROBOT_CALIBRATION", tmp_path / "calibration")
    folders = default_calibration()
    for r, base, make in (
        (FOLLOWER, RobotConfig, make_robot_from_config),
        (LEADER, TeleoperatorConfig, make_teleoperator_from_config),
    ):
        assert r.type in r.checked_types
        for arm_type in r.checked_types:
            config = base.get_choice_class(arm_type)(port="/nonexistent/ttyACM0", id=f"alice_{r.name}")
            arm = make(config)  # type: ignore[arg-type]
            assert calibration_file(folders, r.name, f"alice_{r.name}") == arm.calibration_fpath, arm_type


# --------------------------------------------------------------- find-cameras


class _Capture:
    """cv2.VideoCapture of a camera that opens."""

    def __init__(self, target, *args) -> None:
        self.target = target

    def isOpened(self) -> bool:
        return True

    def get(self, prop) -> float:
        return 0.0

    def getBackendName(self) -> str:
        return "V4L2"

    def release(self) -> None:
        pass


class _Camera:
    is_connected = False

    def read(self):
        return np.zeros((6, 8, 3), dtype=np.uint8)


def test_find_cameras_file_names(settings, monkeypatch):
    camera_opencv = importlib.import_module("lerobot.cameras.opencv.camera_opencv")
    script = importlib.import_module("lerobot.scripts.lerobot_find_cameras")

    class Dev(type(Path())):
        def glob(self, pattern, **kwargs):  # type: ignore[override]
            if str(self) == "/dev":
                return [Path("/dev/video2"), Path("/dev/video0")]
            return super().glob(pattern, **kwargs)

    # lerobot's own discovery on Linux, over two fake /dev/video* devices
    monkeypatch.setattr(camera_opencv.platform, "system", lambda: "Linux")
    monkeypatch.setattr(camera_opencv, "Path", Dev)
    monkeypatch.setattr(camera_opencv.cv2, "VideoCapture", _Capture)
    monkeypatch.setattr(script, "find_all_realsense_cameras", lambda: [])
    monkeypatch.setattr(script, "create_camera_instance", lambda meta, **kw: {"instance": _Camera(), "meta": meta})

    script.save_images_from_all_cameras(settings.root / "frames", record_time_s=0.01)

    images = workspace.captured_images(settings, "frames")
    assert [(i["type"], i["device"], i["width"], i["height"]) for i in images] == [
        ("opencv", "/dev/video0", 8, 6),
        ("opencv", "/dev/video2", 8, 6),
    ]
    stems = sorted(p.stem for p in (settings.root / "frames").iterdir())
    assert [captured_image_device(s) for s in stems] == [("opencv", "/dev/video0"), ("opencv", "/dev/video2")]
