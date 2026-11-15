"""A fake machine (/dev, /sys), a fake lerobot workspace and fake lerobot commands.

Used by the pytest fixtures (tests/conftest.py) and by the end-to-end server (tests/e2e/serve.py).
"""

from __future__ import annotations

import json
import stat
import sys
import textwrap
from pathlib import Path

FOLLOWER_SERIAL = "5A00000001"
LEADER_SERIAL = "5A00000002"
BY_ID = "usb-1a86_USB_Single_Serial_{}-if00"

MOTORS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]


def arm_result(arm: dict, status: str, detail: str = "") -> dict:
    """One arm of a Check arms result, as `adapters.arms.check_arms` reports it."""
    file = f"/calibration/{arm['role']}/{arm['id']}.json"
    return {"role": arm["role"], "port": arm["port"], "id": arm["id"], "file": file, "status": status, "detail": detail}


def calibration(offset: int) -> dict:
    return {
        name: {"id": i + 1, "drive_mode": 0, "homing_offset": offset + i, "range_min": 800 + i, "range_max": 3400 + i}
        for i, name in enumerate(MOTORS)
    }


FOLLOWER_CAL = calibration(-1900)
LEADER_CAL = calibration(400)


def _link(path: Path, target: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target)


def make_fs_root(base: Path) -> Path:
    """/dev and /sys of a PC with an SO-101 follower (ttyACM0) and leader (ttyACM1)."""
    root = base / "fs"
    dev = root / "dev"
    dev.mkdir(parents=True)
    for tty in ("ttyACM0", "ttyACM1", "ttyUSB0"):
        (dev / tty).touch()
    _link(dev / "serial" / "by-id" / BY_ID.format(FOLLOWER_SERIAL), "../../ttyACM0")
    _link(dev / "serial" / "by-id" / BY_ID.format(LEADER_SERIAL), "../../ttyACM1")
    # sysfs: each tty's `device` is the USB interface; the USB device above it has the board's serial
    for tty, port, serial in (("ttyACM0", "1-1", FOLLOWER_SERIAL), ("ttyACM1", "1-2", LEADER_SERIAL)):
        usb = root / "sys" / "devices" / "usb1" / port
        (usb / f"{port}:1.0").mkdir(parents=True)
        (usb / "serial").write_text(f"{serial}\n")
        _link(root / "sys" / "class" / "tty" / tty / "device", f"../../../devices/usb1/{port}/{port}:1.0")
    return root


def _write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if not isinstance(data, str) else data)
    return path


def calibration_folders(base: Path) -> dict[str, Path]:
    """lerobot's calibration folders of robots and teleoperators under `base` (its HF_LEROBOT_CALIBRATION)."""
    return {"robots": base / "robots", "teleoperators": base / "teleoperators"}


def make_workspace(base: Path) -> tuple[Path, Path]:
    """(workspace root, HF_LEROBOT_HOME) with a dataset, calibration files and a training run."""
    root = base / "ws"
    hf_home = root / "lerobot"
    ds = hf_home / "alice" / "pick_place_20260105_093000"
    _write(
        ds / "meta" / "info.json",
        {
            "fps": 30,
            "total_episodes": 150,
            "total_frames": 90000,
            "robot_type": "so_follower",
            "features": {
                "observation.images.top": {"shape": [480, 640, 3], "names": ["height", "width", "channels"]},
                "observation.images.wrist": {"shape": [480, 640, 3], "names": ["height", "width", "channels"]},
                "observation.state": {},
                "action": {},
            },
        },
    )
    import pandas as pd

    pd.DataFrame({"task_index": [0]}, index=pd.Index(["pick up the red cube"], name="task")).to_parquet(
        ds / "meta" / "tasks.parquet"
    )
    _write(hf_home / "bob" / "pick-trial" / "meta" / "info.json", {"fps": 30, "total_episodes": 2, "features": {}})
    _write(hf_home / "calibration" / "robots" / "so_follower" / "my_follower_arm.json", FOLLOWER_CAL)
    _write(hf_home / "calibration" / "teleoperators" / "so_leader" / "my_leader_arm.json", LEADER_CAL)

    # lerobot-train's own layout: outputs/train/<date>/<time>_<job name> in the workspace
    run = root / "outputs" / "train" / "2026-01-06" / "10-15-00_smolvla_pick"
    for step in ("010000", "050000"):
        pm = run / "checkpoints" / step / "pretrained_model"
        _write(
            pm / "config.json",
            {
                "type": "smolvla",
                "chunk_size": 50,
                "n_action_steps": 50,
                "n_obs_steps": 1,
                "input_features": {
                    "observation.state": {"type": "STATE", "shape": [6]},
                    "observation.images.top": {"type": "VISUAL", "shape": [3, 480, 640]},
                    "observation.images.wrist": {"type": "VISUAL", "shape": [3, 480, 640]},
                },
            },
        )
        _write(
            pm / "train_config.json",
            {
                "steps": 50000,
                "dataset": {"repo_id": "alice/pick_place_20260105_093000"},
                "policy": {"type": "smolvla", "pretrained_path": None, "load_vlm_weights": False},
                "trackio": {"enable": True, "project": "pick-demo", "space_id": "alice/trackio"},
                "rename_map": {},
            },
        )
    (run / "checkpoints" / "last").symlink_to("050000")
    return root, hf_home


FAKE_COMMANDS = {
    # waits for Enter like the real one, then reports the port that "disappeared"
    "lerobot-find-port": """
        print("Finding all available ports for the MotorsBus.")
        print("Remove the USB cable from your MotorsBus and press Enter when done.", flush=True)
        input()
        print("The port of this MotorsBus is '/dev/ttyACM1'")
        print("Reconnect the USB cable.")
    """,
    # runs until Ctrl+C, printing a redrawn table like lerobot does
    "lerobot-teleoperate": """
        import signal, sys, time
        signal.signal(signal.SIGINT, lambda *a: (print("stopped", flush=True), sys.exit(130)))
        print("started", " ".join(sys.argv[1:]), flush=True)
        while True:
            print("NAME | NORM\\n" + "\\x1b[2A", end="", flush=True)
            time.sleep(0.05)
    """,
    "lerobot-train": """
        import os, sys
        print("train", " ".join(sys.argv[1:]))
        print("HF_LEROBOT_HOME=" + os.environ["HF_LEROBOT_HOME"])
        print("cwd=" + os.getcwd())
    """,
    "lerobot-record": "import sys; print('record'); sys.exit(3)",
    # `trackio show`: prints the dashboard's address, then serves until Ctrl+C
    "trackio": """
        import signal, sys, time
        signal.signal(signal.SIGINT, lambda *a: (print("closed", flush=True), sys.exit(0)))
        project = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--project=")), "")
        print("args", " ".join(sys.argv[1:]))
        print("\\x1b[1m* Trackio UI launched at: http://127.0.0.1:7860/" + (f"?project={project}" if project else "") + "\\x1b[0m", flush=True)
        while True:
            time.sleep(0.05)
    """,
    "lerobot-rollout": "print('rollout')",
    "lerobot-calibrate": "print('calibrate')",
    # saves a frame of two cameras, named as lerobot names them
    "lerobot-find-cameras": """
        import struct, sys, zlib
        from pathlib import Path
        out = Path("outputs/captured_images")
        for a in sys.argv[1:]:
            if a.startswith("--output-dir="):
                out = Path(a.split("=", 1)[1])
        out.mkdir(parents=True, exist_ok=True)

        def png(path, w, h, rgb):
            def chunk(kind, data):
                return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
            rows = b"".join(b"\\x00" + bytes(rgb) * w for _ in range(h))
            head = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
            path.write_bytes(b"\\x89PNG\\r\\n\\x1a\\n" + chunk(b"IHDR", head) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))

        png(out / "opencv__dev_video0.png", 64, 48, (70, 130, 180))
        png(out / "opencv__dev_video2.png", 64, 48, (200, 120, 60))
        print("find-cameras")
    """,
}


def make_bin_dir(base: Path) -> Path:
    """Executables standing in for the lerobot commands."""
    d = base / "bin"
    d.mkdir()
    for name, body in FAKE_COMMANDS.items():
        script = d / name
        script.write_text(f"#!{sys.executable}\n" + textwrap.dedent(body))
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return d


#: the argument listing of lerobot-find-cameras for the tests that don't use lerobot
FIND_CAMERAS_OPTIONS = {
    "options": [
        {"flag": "camera_type", "kind": "enum", "choices": ["opencv", "realsense"], "default": None,
         "required": False, "optional": True, "type": "str", "help": "", "positional": True},
        {"flag": "output-dir", "kind": "str", "choices": None, "default": "outputs/captured_images",
         "required": False, "optional": True, "type": "Path", "help": "", "positional": False},
        {"flag": "record-time-s", "kind": "float", "choices": None, "default": "6.0",
         "required": False, "optional": True, "type": "float", "help": "", "positional": False},
    ],
    "errors": [],
}  # fmt: skip


def make_hub_cache(cache: Path, repos: list[tuple[str, str, int]]) -> Path:
    """A huggingface_hub cache with (repo type, repo id, file size) entries, laid out as huggingface_hub
    keeps it (blobs, refs/main, snapshots/<commit>/ linking to the blobs)."""
    for i, (repo_type, repo_id, size) in enumerate(repos):
        repo = cache / f"{repo_type}s--{repo_id.replace('/', '--')}"
        commit = f"{i:040x}"
        blob = repo / "blobs" / f"{i:064x}"
        blob.parent.mkdir(parents=True)
        blob.write_bytes(b"x" * size)
        (repo / "refs").mkdir()
        (repo / "refs" / "main").write_text(commit)
        snapshot = repo / "snapshots" / commit
        snapshot.mkdir(parents=True)
        (snapshot / "config.json").symlink_to(f"../../blobs/{blob.name}")
    return cache


def fake_serial_ports(fs_root: Path):
    """What pyserial would list on the fake machine: its /dev/ttyACM* and /dev/ttyUSB*, with the
    serial number in the fake sysfs (the ACM boards are CH343s, the USB one an FTDI without serial)."""
    import os

    from lerobot_gui.devices import SerialPort

    out = []
    dev = fs_root / "dev"
    for tty in sorted([*dev.glob("ttyACM*"), *dev.glob("ttyUSB*")]) if dev.is_dir() else []:
        node = fs_root / "sys" / "class" / "tty" / tty.name / "device"
        try:
            serial = (Path(os.path.realpath(node)).parent / "serial").read_text().strip() or None
        except OSError:
            serial = None
        vid, pid = (0x1A86, 0x55D3) if tty.name.startswith("ttyACM") else (0x0403, 0x6001)
        out.append(SerialPort(f"/dev/{tty.name}", vid, pid, serial, "USB Single Serial"))
    return out
