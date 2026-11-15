"""Serial ports (the arms' USB motor boards) and calibration files on this machine.

The ports come from pyserial; `fs_root` (normally `/`) is where /dev/serial/by-id is read, so tests
can point it at a fake tree.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


def natural_key(text: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]


def _dev_path(fs_root: Path, path: Path) -> str:
    """`path` (inside fs_root) as the absolute device path a program would use."""
    return "/" + str(path.relative_to(fs_root)).lstrip("/")


def _real(fs_root: Path, link: Path) -> str:
    """Where a symlink points, as a device path relative to fs_root."""
    target = Path(os.path.realpath(link))
    try:
        return _dev_path(fs_root, target)
    except ValueError:
        return str(target)


@dataclass(frozen=True)
class SerialPort:
    """A serial port as pyserial lists it (the fields the GUI uses)."""

    device: str
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    description: str | None = None


def list_serial_ports(fs_root: Path) -> list[SerialPort]:
    """The serial ports pyserial finds on this computer (Linux, macOS, Windows). The tests replace
    this with a reader of their fake tree under `fs_root`."""
    from serial.tools import list_ports

    return [SerialPort(p.device, p.vid, p.pid, p.serial_number or None, p.description) for p in list_ports.comports()]


def _lerobot_name(device: str) -> str:
    """The name lerobot-find-port reports: on macOS the /dev/tty.* node of the /dev/cu.* one."""
    return "/dev/tty." + device[len("/dev/cu.") :] if device.startswith("/dev/cu.") else device


def ports(fs_root: Path = Path("/")) -> list[dict]:
    """The USB serial ports (the arms' motor boards), one entry each:

    - `tty`: the device as lerobot-find-port names it (`/dev/ttyACM0`, `/dev/tty.usbmodem…`, `COM3`)
    - `aliases`: every name of it (`tty`, macOS's /dev/cu.* node, Linux's /dev/serial/by-id link)
    - `board`: the identity of the USB-serial board on it, which stays the same when the port is
      renumbered: its /dev/serial/by-id link on Linux, else `usb:<vid>:<pid>:<serial>`; None
      without a serial number
    - `serial`: the serial number the board reports, or None

    The ports come from pyserial (`list_serial_ports`); the by-id links from `fs_root`.
    """
    by_id: dict[str, str] = {}
    by_id_dir = fs_root / "dev" / "serial" / "by-id"
    for link in sorted(by_id_dir.glob("*")) if by_id_dir.is_dir() else []:
        by_id.setdefault(_real(fs_root, link), _dev_path(fs_root, link))
    out = []
    for p in list_serial_ports(fs_root):
        if p.vid is None:  # not USB: a built-in serial port, Bluetooth...
            continue
        tty = _lerobot_name(p.device)
        link = by_id.get(p.device)
        usb = f"usb:{p.vid:04x}:{p.pid or 0:04x}:{p.serial_number}" if p.serial_number else None
        aliases = list(dict.fromkeys(x for x in (tty, p.device, link) if x))
        out.append({"tty": tty, "aliases": aliases, "board": link or usb, "serial": p.serial_number})
    return sorted(out, key=lambda x: natural_key(x["tty"]))
