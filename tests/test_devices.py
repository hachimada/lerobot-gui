from lerobot_gui import devices
from lerobot_gui.adapters import lerobot_files

from .conftest import BY_ID, FOLLOWER_SERIAL, LEADER_SERIAL, calibration_folders


def test_ports_are_ttys_with_their_board_and_its_serial(fs_root):
    follower = f"/dev/serial/by-id/{BY_ID.format(FOLLOWER_SERIAL)}"
    leader = f"/dev/serial/by-id/{BY_ID.format(LEADER_SERIAL)}"
    assert devices.ports(fs_root) == [
        {"tty": "/dev/ttyACM0", "aliases": ["/dev/ttyACM0", follower], "board": follower, "serial": FOLLOWER_SERIAL},
        {"tty": "/dev/ttyACM1", "aliases": ["/dev/ttyACM1", leader], "board": leader, "serial": LEADER_SERIAL},
        # no by-id link and no serial number: nothing tells the board apart
        {"tty": "/dev/ttyUSB0", "aliases": ["/dev/ttyUSB0"], "board": None, "serial": None},
    ]


def test_a_board_serial_is_what_the_board_reports_not_its_name(fs_root):
    link = fs_root / "dev" / "serial" / "by-id" / BY_ID.format(FOLLOWER_SERIAL)
    link.rename(link.with_name("usb-Some_Board-if00"))  # a name without the serial in it
    (follower,) = [p for p in devices.ports(fs_root) if p["tty"] == "/dev/ttyACM0"]
    assert (follower["board"], follower["serial"]) == ("/dev/serial/by-id/usb-Some_Board-if00", FOLLOWER_SERIAL)


def _listed(monkeypatch, *found):
    monkeypatch.setattr(devices, "list_serial_ports", lambda fs_root: list(found))


def test_macos_ports_are_named_as_lerobot_find_port_names_them(monkeypatch, tmp_path):
    _listed(
        monkeypatch,
        devices.SerialPort("/dev/cu.usbmodem5A00000011", 0x1A86, 0x55D3, "5A00000011"),
        devices.SerialPort("/dev/cu.Bluetooth-Incoming-Port"),  # not USB: left out
    )
    assert devices.ports(tmp_path) == [
        {
            "tty": "/dev/tty.usbmodem5A00000011",  # the /dev/tty.* node, as lerobot-find-port reports it
            "aliases": ["/dev/tty.usbmodem5A00000011", "/dev/cu.usbmodem5A00000011"],
            "board": "usb:1a86:55d3:5A00000011",  # no /dev/serial/by-id: the USB ids and serial
            "serial": "5A00000011",
        }
    ]


def test_windows_ports(monkeypatch, tmp_path):
    _listed(
        monkeypatch,
        devices.SerialPort("COM10", 0x1A86, 0x55D3, "5A00000012"),
        devices.SerialPort("COM3", 0x0403, 0x6001, None),
    )
    assert [(p["tty"], p["board"]) for p in devices.ports(tmp_path)] == [
        ("COM3", None),
        ("COM10", "usb:1a86:55d3:5A00000012"),
    ]


def test_the_ports_come_from_pyserial(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from serial.tools import list_ports

    listed = [SimpleNamespace(device="/dev/ttyACM7", vid=0x1A86, pid=0x55D3, serial_number="", description="x")]
    monkeypatch.undo()  # take back the tests' fake of list_serial_ports (conftest)
    monkeypatch.setattr(list_ports, "comports", lambda: listed)
    assert devices.list_serial_ports(tmp_path) == [devices.SerialPort("/dev/ttyACM7", 0x1A86, 0x55D3, None, "x")]


def test_ports_empty_without_dev(tmp_path):
    assert devices.ports(tmp_path) == []


def test_calibrations(workspace, tmp_path):
    _, hf_home = workspace
    assert lerobot_files.calibrations(calibration_folders(hf_home / "calibration")) == {
        "robots": [{"class": "so_follower", "id": "my_follower_arm"}],
        "teleoperators": [{"class": "so_leader", "id": "my_leader_arm"}],
    }
    # the folders lerobot reports (HF_LEROBOT_CALIBRATION elsewhere), not a place under HF_LEROBOT_HOME
    elsewhere = calibration_folders(tmp_path / "calibration-elsewhere")
    (elsewhere["teleoperators"] / "so_leader").mkdir(parents=True)
    (elsewhere["teleoperators"] / "so_leader" / "alice_leader.json").write_text("{}")
    assert lerobot_files.calibrations(elsewhere) == {
        "robots": [],
        "teleoperators": [{"class": "so_leader", "id": "alice_leader"}],
    }


def test_natural_key_orders_numbers_numerically():
    assert sorted(["video10", "video2", "video1"], key=devices.natural_key) == ["video1", "video2", "video10"]
