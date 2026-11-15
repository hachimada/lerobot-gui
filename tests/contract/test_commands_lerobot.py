"""Contract tests: the command lines the pages build are parsed by the installed lerobot itself.

Each scenario builds a command from page values, runs it through lerobot's own CLI parsing
(`lerobot.configs.parser.wrap`, with sys.argv patched, as the console script does) and checks that
every flag ended up in the parsed config. A flag lerobot renamed or removed fails here first.
Whether lerobot then runs the command is lerobot's business, not checked here.
"""

from __future__ import annotations

import enum
import importlib
import json
import sys
from collections.abc import Callable
from typing import Any, cast

import pytest
from pydantic import TypeAdapter

pytest.importorskip("lerobot")
pytestmark = pytest.mark.lerobot

from lerobot_gui import commands  # noqa: E402
from lerobot_gui.adapters.cameras import LEROBOT  # noqa: E402
from lerobot_gui.adapters.options import CONFIG_COMMANDS, list_options  # noqa: E402
from lerobot_gui.adapters.roles import FOLLOWER, LEADER, types  # noqa: E402
from lerobot_gui.schemas import OptionsListing  # noqa: E402

from ..commands_helpers import CAMERAS, build, flags  # noqa: E402


def lerobot_listing(command: str, selections: dict[str, str], policy_path: str | None) -> dict:
    return list_options(command, selections, policy_path)


RUN = "outputs/train/2026-01-06/10-15-00_smolvla_pick/checkpoints"
LAST = f"{RUN}/last/pretrained_model"
DATASET = "alice/pick_place_20260105_093000"
#: hardware with the top camera named "front": the policy saw it as "top"
FRONT = [
    {"name": "front", "type": "opencv", "device": "/dev/video0", "settings": {"width": 640, "height": 480, "fps": 30}}
]
RENAME = '{"observation.images.front": "observation.images.top"}'


@pytest.fixture
def real_checkpoints(settings):
    """Replace the fixture's hand-written checkpoint configs with ones lerobot saved itself."""
    from lerobot.policies.smolvla.configuration_smolvla import SmolVLAConfig

    for step in ("010000", "050000"):
        pm = settings.root / RUN / step / "pretrained_model"
        features = json.loads((pm / "config.json").read_text())["input_features"]
        (pm / "config.json").unlink()
        SmolVLAConfig()._save_pretrained(pm)
        cfg = json.loads((pm / "config.json").read_text())
        cfg["input_features"] = features
        (pm / "config.json").write_text(json.dumps(cfg))
        # train_config.json holds the whole policy config, as lerobot-train saves it
        train = json.loads((pm / "train_config.json").read_text())
        train["policy"] = {**cfg, "push_to_hub": False, "pretrained_path": None}
        (pm / "train_config.json").write_text(json.dumps(train))
    return settings


def parse(command: str, args: list[str], monkeypatch) -> Any:
    """Parse `args` the way the lerobot console script does."""
    from lerobot.configs import parser

    register_mod, cfg_mod, cfg_name = CONFIG_COMMANDS[command]
    importlib.import_module(register_mod)
    cls = getattr(importlib.import_module(cfg_mod), cfg_name)
    monkeypatch.setattr(sys, "argv", [command, *args])

    def main(cfg):
        return cfg

    main.__annotations__ = {"cfg": cls}
    cfg = cast(Callable[[], Any], parser.wrap()(main))()  # the CLI calls it without arguments
    if hasattr(cfg, "validate"):
        cfg.validate()  # lerobot-train validates right after parsing
    return cfg


def lookup(cfg: object, flag: str) -> object:
    obj = cfg
    for part in flag.split("."):
        obj = obj[part] if isinstance(obj, dict) else getattr(obj, part)
    return obj


def same(parsed: object, given: str) -> bool:
    if isinstance(parsed, bool):
        return given == ("true" if parsed else "false")
    if isinstance(parsed, enum.Enum):
        return given in (parsed.name, str(parsed.value))
    if isinstance(parsed, int | float):
        return float(given) == float(parsed)
    if isinstance(parsed, list | tuple):
        return json.loads(given) == list(parsed)
    if isinstance(parsed, dict):
        return json.loads(given) == parsed
    return str(parsed) == given


def assert_applied(cfg: object, args: list[str]) -> None:
    """Every flag of the command line is what the parsed config holds."""
    for flag, value in flags(args).items():
        if flag in ("policy.path", "config_path"):
            continue  # consumed by lerobot to load the pretrained config
        if flag.endswith(".type"):
            obj = lookup(cfg, flag.removesuffix(".type"))
            # (several names can share a class, e.g. so100_follower and so101_follower)
            assert type(obj).get_choice_class(value) is type(obj), flag  # type: ignore[attr-defined]
            continue
        parsed = lookup(cfg, flag)
        if flag == "robot.cameras":
            assert set(parsed) == {c.split(":")[0].strip("{ ") for c in value.split("}, ")}  # type: ignore[arg-type]
            continue
        assert same(parsed, value), f"--{flag}={value} parsed as {parsed!r}"


SO101 = types(FOLLOWER, LEADER)

SCENARIOS = [
    ("calibrate", {}),
    ("calibrate", {"gui.target": "leader"}),
    ("teleoperate", {}),
    ("teleoperate", {"gui.cameras": "none", "robot.max_relative_target": 10, "display_data": False, "fps": 30, "teleop_time_s": 12.5}),
    (
        "record",
        {
            "dataset.repo_id": "alice/rec", "dataset.single_task": "pick", "dataset.num_episodes": 3,
            "dataset.episode_time_s": 30, "dataset.reset_time_s": 10, "dataset.fps": 15, "dataset.push_to_hub": False,
            "robot.max_relative_target": 5, "display_data": True,
        },
    ),
    (
        "record",
        {
            "dataset.repo_id": DATASET, "resume": True, "dataset.root": f"lerobot/{DATASET}", "dataset.single_task": "t",
            "dataset.streaming_encoding": True, "dataset.encoder_threads": 2, "play_sounds": False,
        },
    ),
    # adding to a local dataset with the folder left empty: the GUI writes the dataset's folder
    ("record", {"dataset.repo_id": DATASET, "resume": True, "dataset.single_task": "t"}),
    (
        "train",
        {"gui.mode": "new", "policy.type": "act", "dataset.repo_id": DATASET, "policy.n_action_steps": 50,
         "num_workers": 12, "policy.push_to_hub": False},
    ),
    (
        "train",
        {"gui.mode": "new", "policy.type": "diffusion", "dataset.repo_id": DATASET, "policy.use_amp": True,
         "policy.push_to_hub": "false", "steps": 1000, "batch_size": 4},
    ),
    (
        "train",
        {
            "gui.mode": "finetune", "policy.path": LAST, "dataset.repo_id": DATASET, "dataset.episodes": "0-2,5",
            "dataset.eval_split": 0.1, "eval_steps": 500, "dataset.image_transforms.enable": True, "save_freq": 5000,
            "log_freq": 50, "seed": 7, "policy.device": "cpu", "policy.optimizer_lr": 0.0001,
            "output_dir": "outputs/train/new_run", "job_name": "pick", "policy.push_to_hub": True,
            "policy.repo_id": "alice/pick_smolvla", "trackio.enable": True, "trackio.project": "so101",
            "trackio.space_id": "alice/trackio", "trackio.private": True,
            "rename_map": '{"observation.images.top": "observation.images.top"}',
        },
    ),
    ("train", {"gui.mode": "resume", "config_path": f"{LAST}/train_config.json", "steps": 80000}),
    (
        "rollout",
        {"policy.path": LAST, "task": "x", "policy.n_action_steps": 25, "duration": 30, "display_data": True,
         "return_to_initial_position": False, "interpolation_multiplier": 2, "device": "cpu"},
    ),
    (
        "rollout",
        {"policy.path": LAST, "inference.type": "rtc", "inference.queue_threshold": 20,
         "inference.rtc.execution_horizon": 8, "inference.rtc.max_guidance_weight": 5,
         "inference.rtc.prefix_attention_schedule": "EXP"},
    ),
    (
        "rollout",
        {"policy.path": LAST, "strategy.type": "episodic", "gui.leader": "use", "dataset.repo_id": "alice/rollout_eval",
         "dataset.num_episodes": 2, "dataset.episode_time_s": 20, "dataset.reset_time_s": 5, "dataset.push_to_hub": False},
    ),
    (
        "rollout",
        {"policy.path": LAST, "strategy.type": "dagger", "gui.leader": "use", "strategy.record_autonomous": True,
         "dataset.repo_id": "alice/rollout_fix", "dataset.num_episodes": 4},
    ),
    (
        "rollout",
        {"policy.path": LAST, "strategy.type": "sentry", "strategy.upload_every_n_episodes": 3,
         "dataset.repo_id": "alice/rollout_watch", "dataset.streaming_encoding": True, "dataset.encoder_threads": 2},
    ),
    (
        "rollout",
        {"policy.path": LAST, "strategy.type": "highlight", "strategy.ring_buffer_seconds": 20,
         "dataset.repo_id": "alice/rollout_hl", "fps": 15, "dataset.fps": 15, "use_torch_compile": True,
         "play_sounds": False},
    ),
    ("rollout", {"policy.path": LAST, "rename_map": RENAME}, {"cameras": [*FRONT, CAMERAS[1]]}),
]  # fmt: skip


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[f"{s[0]}-{i}" for i, s in enumerate(SCENARIOS)])
def test_built_commands_parse_in_lerobot(real_checkpoints, monkeypatch, scenario):
    settings = real_checkpoints
    page, values, *hw = scenario
    monkeypatch.chdir(settings.root)  # the GUI runs commands from the workspace
    args, m = build(settings, page, values, hw=hw[0] if hw else None, listing=lerobot_listing, cameras=LEROBOT)
    assert m.errors == 0, m.texts("err")
    entered = {k for k, v in values.items() if not k.startswith("gui.")}
    written = {a[2:].split("=", 1)[0] for a in args if a.startswith("--")}
    assert entered <= written, f"not written: {entered - written}"  # every value entered is in the command
    cfg = parse(commands.get_page(page).exe, args, monkeypatch)  # type: ignore[arg-type]
    assert_applied(cfg, args)


def test_find_cameras_arguments_parse(settings, monkeypatch):
    mod = importlib.import_module("lerobot.scripts.lerobot_find_cameras")
    seen = []
    monkeypatch.setattr(mod, "save_images_from_all_cameras", lambda **kw: seen.append(kw))
    for values in ({}, {"camera_type": "opencv", "output-dir": "outputs/x", "record-time-s": 2.5}):
        args, m = build(settings, "find-cameras", values)
        assert m.errors == 0
        monkeypatch.setattr(sys, "argv", ["lerobot-find-cameras", *args])
        mod.main()
    assert [(k["camera_type"], str(k["output_dir"]), k["record_time_s"]) for k in seen] == [
        (None, "outputs/captured_images", 2.0),
        ("opencv", "outputs/x", 2.5),
    ]


#: selections under which every field of a page is a lerobot option
LISTED_UNDER = {
    "calibrate": [{"robot": "so101_follower"}, {"teleop": "so101_leader"}],
    "teleoperate": [SO101],
    "record": [SO101],
    "train": [{"policy": "act"}],
    "rollout": [
        {**SO101, "policy": "act", "strategy": s, "inference": i}
        for s in ("base", "episodic", "dagger", "sentry", "highlight")
        for i in ("sync", "rtc")
    ],
}
#: read by lerobot's parser before its config (the pretrained config to load)
PATH_FLAGS = {"policy.path", "config_path"}


@pytest.mark.parametrize("page_id", sorted(LISTED_UNDER))
def test_every_field_is_a_lerobot_option(page_id):
    page = commands.get_page(page_id)
    assert page.exe
    listed: dict[str, dict] = {}
    for selections in LISTED_UNDER[page_id]:
        listed.update({o["flag"]: o for o in list_options(page.exe, selections)["options"]})
    for f in page.fields():
        if not f.is_flag or f.positional or f.key in PATH_FLAGS:
            continue
        assert f.key in listed, f"{page_id}: `--{f.key}` is not a {page.exe} option any more"
        if f.lerobot_choices:
            assert listed[f.key]["choices"], f"{page_id}: `--{f.key}` has no choices"


def test_every_camera_type_is_read_from_lerobot():
    types = LEROBOT.types()
    assert "opencv" in types
    for cam_type in types:
        fields = {f["flag"]: f for f in LEROBOT.fields(cam_type)}
        assert {"fps", "width", "height"} <= set(fields), cam_type  # lerobot's CameraConfig
        device = LEROBOT.device_field(cam_type)
        assert device is None or fields[device]["required"], cam_type
    assert LEROBOT.device_field("opencv") == "index_or_path"


def test_cameras_written_with_lerobots_choices_parse(settings, monkeypatch):
    fields = {f["flag"]: f for f in LEROBOT.fields("opencv")}
    picked = {k: fields[k]["choices"][1] for k in ("rotation", "color_mode", "backend")}  # not the defaults
    cam = {
        "name": "top",
        "type": "opencv",
        "device": "/dev/video0",
        "settings": {"width": 640, "height": 480, "fps": 30, "warmup_s": 2, "fourcc": "MJPG", **picked},
    }
    args, m = build(settings, "teleoperate", hw={"cameras": [cam]}, cameras=LEROBOT)
    assert m.errors == 0, m.texts("err")
    monkeypatch.chdir(settings.root)
    parsed = parse("lerobot-teleoperate", args, monkeypatch).robot.cameras["top"]
    assert (parsed.width, parsed.height, parsed.fps, parsed.warmup_s, parsed.fourcc) == (640, 480, 30, 2, "MJPG")
    assert str(parsed.index_or_path) == "/dev/video0"
    for key, name in picked.items():
        assert getattr(parsed, key).name == name, key


@pytest.mark.parametrize(
    "name",
    ["top cam", "wrist: 2", 'say "cheese"', "it's", "前方", "1", "true", "null", "on", "1.0", "0x10", "~", "1e3", "-"],
)
def test_any_camera_name_parses(settings, monkeypatch, name):
    cam = {
        "name": name,
        "type": "opencv",
        "device": "/dev/video0",
        "settings": {"width": 640, "height": 480, "fps": 30},
    }
    args, m = build(settings, "teleoperate", hw={"cameras": [cam]}, cameras=LEROBOT)
    assert m.errors == 0, m.texts("err")
    monkeypatch.chdir(settings.root)
    assert list(parse("lerobot-teleoperate", args, monkeypatch).robot.cameras) == [name]


def test_find_cameras_arguments_are_read_from_lerobot():
    import argparse as real_argparse

    module = importlib.import_module("lerobot.scripts.lerobot_find_cameras")
    listing = list_options("lerobot-find-cameras")
    TypeAdapter(OptionsListing).validate_python(listing)  # the shape the API declares
    found = {o["flag"]: o for o in listing["options"]}
    assert found["camera_type"]["positional"] and "opencv" in found["camera_type"]["choices"]
    assert found["output-dir"]["default"] and found["record-time-s"]["kind"] == "float"
    assert module.argparse is real_argparse  # the script's own reference is put back
    from lerobot_gui.workspace import default_capture_dir

    assert default_capture_dir() == found["output-dir"]["default"]
    fields = {f.key for f in commands.get_page("find-cameras").fields()}
    assert fields <= set(found)  # every field is one of its arguments


def test_the_devices_offered_are_ones_lerobot_takes():
    from lerobot.utils.device_utils import is_torch_device_available

    from lerobot_gui.adapters.torch_devices import available

    found = [d["value"] for d in available()]
    assert found[-1] == "cpu"
    assert all(is_torch_device_available(d) for d in found)  # also: no name lerobot refuses
