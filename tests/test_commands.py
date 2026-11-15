"""The command pages: only entered values are written; lerobot checks the rest (no lerobot needed here)."""

import json
from typing import Any

import pytest

from lerobot_gui import commands
from lerobot_gui.commands import domain, hardware
from lerobot_gui.commands.model import Messages

from .commands_helpers import CAMERAS, HARDWARE, LOGGED_IN, build, context, flags, listing
from .conftest import BY_ID, FOLLOWER_SERIAL, LEADER_SERIAL

FOLLOWER_BOARD = f"/dev/serial/by-id/{BY_ID.format(FOLLOWER_SERIAL)}"
LEADER_BOARD = f"/dev/serial/by-id/{BY_ID.format(LEADER_SERIAL)}"
RUN = "outputs/train/2026-01-06/10-15-00_smolvla_pick/checkpoints"
LAST = f"{RUN}/last/pretrained_model"
DATASET = "alice/pick_place_20260105_093000"
FOLLOWER = ["--robot.type=so101_follower", "--robot.port=/dev/ttyACM0", "--robot.id=my_follower_arm"]
LEADER = ["--teleop.type=so101_leader", "--teleop.port=/dev/ttyACM1", "--teleop.id=my_leader_arm"]


def errors(m: Messages) -> list[str]:
    return m.texts("err")


def actions(m: Messages) -> list[Any]:
    return [a for msg in m.items for a in msg.actions]


def hardware_fields(settings, **hw) -> dict[str, Any]:
    """The Hardware page's fields (each arm's port and id) by key."""
    groups = hardware.form(context(settings, "", hw=hw or None))["groups"]
    return {f["key"]: f for g in groups for f in g["fields"]}


def fields_of(settings, page, values=None, *, listing=None, accounts=None) -> dict[str, Any]:
    ctx = context(settings, page, values, accounts=accounts)
    out = commands.form(commands.get_page(page), ctx, listing or commands.no_listing)
    return {f["key"]: f for g in out["groups"] for f in g["fields"]}


# ------------------------------------------------------- only entered values


def test_nothing_entered_writes_only_the_hardware(settings):
    args, m = build(settings, "teleoperate")
    assert args[:6] == FOLLOWER + LEADER
    assert [a.split("=")[0] for a in args[6:]] == ["--robot.cameras"]
    assert errors(m) == []
    for page in ("record", "rollout", "calibrate"):
        args, _ = build(settings, page)
        assert all(a.split("=")[0].startswith(("--robot.", "--teleop.")) for a in args), page
    assert build(settings, "train")[0] == []
    assert build(settings, "find-cameras")[0] == []


def test_entered_values_are_written_as_typed(settings):
    values = {"fps": "30", "teleop_time_s": 12.5, "display_data": "false", "robot.max_relative_target": "", "x": None}
    args, m = build(settings, "teleoperate", values)
    f = flags(args)
    assert f["fps"] == "30" and f["teleop_time_s"] == "12.5"
    assert f["display_data"] == "false"  # entered false is written: it isn't compared with lerobot's default
    assert "robot.max_relative_target" not in f  # empty: lerobot's default
    assert errors(m) == []


def test_booleans_take_true_false_or_nothing(settings):
    for value, written in ((True, "true"), ("TRUE", "true"), (False, "false")):
        assert flags(build(settings, "record", {"display_data": value})[0])["display_data"] == written
    _, m = build(settings, "record", {"display_data": "yes"})
    assert errors(m) == ["Show in Rerun: `yes` is not true or false."]


def test_a_toggle_writes_true_when_on_and_nothing_when_off(settings):
    assert flags(build(settings, "record", {"resume": True})[0])["resume"] == "true"
    for off in (None, False, "false"):
        assert "resume" not in flags(build(settings, "record", {"resume": off})[0])


def test_record_starts_its_dataset_panel_with_the_add_toggle(settings):
    page = commands.get_page("record")
    first = page.groups[0]
    assert first.title == "Dataset"
    assert (first.fields[0].key, first.fields[0].kind) == ("resume", "toggle")


def test_numbers_are_checked_for_format_only(settings):
    _, m = build(settings, "teleoperate", {"fps": "fast"})
    assert errors(m) == ["Loop rate (Hz): `fast` is not a valid number."]
    # whole numbers when lerobot's option is an int
    ints = listing({"flag": "fps", "kind": "int", "default": "60"})
    _, m = build(settings, "teleoperate", {"fps": "1.5"}, listing=ints)
    assert errors(m) == ["Loop rate (Hz): `1.5` is not a valid integer."]


def test_required_comes_from_lerobot(settings):
    required = listing(
        {"flag": "dataset.repo_id", "required": True}, {"flag": "steps", "kind": "int", "default": "100000"}
    )
    _, m = build(settings, "train", listing=required)
    assert errors(m) == ["Dataset (`--dataset.repo_id`) is required."]
    _, m = build(settings, "train", {"dataset.repo_id": DATASET}, listing=required)
    assert errors(m) == []


def test_fields_show_lerobots_defaults_and_choices(settings):
    lerobot = listing(
        {"flag": "strategy.type", "kind": "choice", "choices": ["base", "dagger", "episodic"], "default": "base"},
        {"flag": "fps", "kind": "float", "default": "30.0"},
        {"flag": "display_data", "kind": "bool", "default": "false"},
        {"flag": "dataset.repo_id", "default": ""},
    )
    fields = fields_of(settings, "rollout", {"strategy.type": "episodic"}, listing=lerobot)
    assert [o["value"] for o in fields["strategy.type"]["options"]] == ["base", "dagger", "episodic"]
    assert fields["strategy.type"]["default"] == "base"
    assert fields["fps"]["default"] == "30.0" and fields["fps"]["value"] is None
    assert fields["display_data"]["kind"] == "bool" and fields["display_data"]["flag"] == "--display_data"
    assert fields["dataset.repo_id"]["default"] is None  # lerobot's "" says nothing: the example shows
    # a flag lerobot doesn't list for this selection isn't offered...
    assert "task" not in fields
    # ...except the pretrained path, which lerobot's parser reads before the config
    assert "policy.path" in fields
    args, _ = build(settings, "rollout", {"policy.path": LAST}, listing=lerobot)
    assert f"--policy.path={LAST}" in args
    assert "task" in fields_of(settings, "rollout")  # (listing not read yet: everything shows)


def test_values_of_hidden_fields_are_not_written(settings):
    values = {"gui.mode": "finetune", "policy.type": "act", "policy.path": "lerobot/smolvla_base"}
    f = flags(build(settings, "train", values)[0])
    assert f["policy.path"] == "lerobot/smolvla_base"
    assert "policy.type" not in f  # entered in "New policy", which isn't selected


# -------------------------------------------------------------- GUI choices


def test_calibrate_the_follower_or_the_leader(settings):
    assert build(settings, "calibrate")[0] == FOLLOWER
    assert build(settings, "calibrate", {"gui.target": "leader"})[0] == LEADER
    assert fields_of(settings, "calibrate")["gui.target"]["help"] == (
        "There is a calibration file for `my_follower_arm`; the follower is on `ttyACM0`."
    )


def test_teleoperate_cameras_can_be_left_out(settings):
    args, _ = build(settings, "teleoperate", {"gui.cameras": "none"})
    assert "robot.cameras" not in flags(args)
    fields = fields_of(settings, "teleoperate")
    assert fields["gui.cameras"]["gui"] is True and fields["gui.cameras"]["value"] == "use"


def test_rollout_offers_the_rename_map_the_policy_was_trained_with(settings):
    assert fields_of(settings, "rollout", {"policy.path": LAST})["rename_map"]["suggest"] == []  # trained without one
    trained = {
        "observation.images.wrist": "observation.images.camera1",
        "observation.images.top": "observation.images.camera2",
    }
    config = settings.root / LAST / "train_config.json"
    config.write_text(json.dumps({**json.loads(config.read_text()), "rename_map": trained}))

    field = fields_of(settings, "rollout", {"policy.path": LAST})["rename_map"]
    assert field["suggest"] == [json.dumps(trained)]
    assert field["help"].startswith("Offered: the rename map this policy was trained with")
    # the same map, typed another way: nothing more to offer
    typed = json.dumps(dict(reversed(trained.items())), separators=(",", ":"))
    field = fields_of(settings, "rollout", {"policy.path": LAST, "rename_map": typed})["rename_map"]
    assert field["suggest"] == [] and field["help"].startswith("The rename map this policy was trained with")
    # another map typed: the trained one is still offered
    other = '{"observation.images.top": "observation.images.cam0"}'
    assert fields_of(settings, "rollout", {"policy.path": LAST, "rename_map": other})["rename_map"]["suggest"] == [
        json.dumps(trained)
    ]
    # a model from the Hub: nothing is known about its training
    field = fields_of(settings, "rollout", {"policy.path": "lerobot/smolvla_base"})["rename_map"]
    assert field["suggest"] == [] and field["help"] is None


def test_trackio_shows_the_dashboard_of_a_project_logged_here(settings):
    args, m = build(settings, "trackio")
    assert args == ["show"] and not m.items
    args, _ = build(settings, "trackio", {"project": "pick-demo"})
    assert args == ["show", "--project=pick-demo"]
    out: Any = commands.form(commands.get_page("trackio"), context(settings, "trackio", {"project": "other"}))
    assert out["command"]["preview"] == "uv run trackio \\\n    show \\\n    --project=other"
    field = fields_of(settings, "trackio")["project"]
    assert field["suggest"] == ["pick-demo"]  # the project of the run logged here
    assert "[Trackio](#trackio)" in fields_of(settings, "train")["trackio.enable"]["help"]


def test_rollout_passes_the_leader_when_asked(settings):
    assert "teleop.type" not in flags(build(settings, "rollout")[0])
    args, _ = build(settings, "rollout", {"gui.leader": "use", "strategy.type": "dagger"})
    assert args[-1] == "--strategy.type=dagger"
    assert set(LEADER) <= set(args)


def test_train_resume_adds_resume_true(settings):
    values = {"gui.mode": "resume", "config_path": f"{LAST}/train_config.json", "steps": "80000"}
    args, m = build(settings, "train", values)
    assert args == ["--resume=true", f"--config_path={LAST}/train_config.json", "--steps=80000"]
    assert [
        g["title"] for g in commands.form(commands.get_page("train"), context(settings, "train", values))["groups"]
    ] == ["Policy"]
    assert errors(m) == []


def test_find_cameras_type_is_positional(settings):
    args, _ = build(
        settings, "find-cameras", {"camera_type": "opencv", "output-dir": "outputs/x", "record-time-s": 2.5}
    )
    assert args == ["opencv", "--output-dir=outputs/x", "--record-time-s=2.5"]


# --------------------------------------------------------- converting input


def test_episodes_and_rename_maps_are_written_the_way_lerobot_reads_them(settings):
    values = {
        "gui.mode": "finetune",
        "dataset.episodes": "0-2, 5",
        "rename_map": '{"observation.images.top":"observation.images.camera1"}',
    }
    f = flags(build(settings, "train", values)[0])
    assert f["dataset.episodes"] == "[0,1,2,5]"
    assert f["rename_map"] == '{"observation.images.top": "observation.images.camera1"}'
    _, m = build(settings, "train", {"dataset.episodes": "3-1", "rename_map": "[1]"})
    assert errors(m) == [
        'Rename map: must be a JSON object, e.g. `{"observation.images.top": "observation.images.camera1"}`.',
        "Episodes: use e.g. `0-39`, `0,1,2` or `[0,1,2]`.",
    ]
    assert domain.episode_list("[1, 2]", Messages(), "") == "[1, 2]"


# --------------------------------------------------------------- suggestions


def test_record_suggests_names_folders_and_tasks(settings):
    fields = fields_of(settings, "record", accounts=LOGGED_IN)
    # the account and its organizations, then the namespaces found on disk
    assert fields["dataset.repo_id"]["suggest"] == ["alice/", "team/", "bob/"]
    fields = fields_of(settings, "record", {"resume": True, "dataset.repo_id": DATASET})
    assert "bob/pick-trial" in fields["dataset.repo_id"]["suggest"]
    assert fields["dataset.root"]["suggest"] == [f"lerobot/{DATASET}"]
    assert fields["dataset.single_task"]["suggest"] == ["pick up the red cube"]


def test_rollout_suggests_the_training_task_and_describes_the_policy(settings):
    fields = fields_of(settings, "rollout", {"policy.path": LAST})
    assert fields["task"]["suggest"] == ["pick up the red cube"]
    assert fields["policy.path"]["help"].startswith("smolvla · chunk 50")
    picker = fields["policy.path"]
    assert picker["kind"] == "picker" and picker["hub"] is True
    assert [o["group"] for o in picker["options"]] == ["outputs/train/2026-01-06/10-15-00_smolvla_pick"]
    assert [i["value"] for i in picker["options"][0]["items"]] == [
        LAST,
        f"{RUN}/050000/pretrained_model",
        f"{RUN}/010000/pretrained_model",
    ]
    train = fields_of(settings, "train", {"gui.mode": "finetune"})["policy.path"]
    assert train["kind"] == "picker" and train["options"] == picker["options"]


# ------------------------------------------------------------------- extras


EXTRA_LISTING = listing(
    {"flag": "robot.port"},
    {"flag": "robot.use_degrees", "kind": "bool"},
    {"flag": "display_mode", "kind": "enum", "choices": ["rerun", "foxglove"]},
    {"flag": "teleop_time_s", "kind": "float"},
)


def test_all_options_values_are_written_when_lerobot_lists_them(settings):
    values = {"robot.use_degrees": "true", "display_mode": "web", "robot.port": "/dev/x", "gone": "1"}
    args, m = build(settings, "teleoperate", values, listing=EXTRA_LISTING)
    assert "--robot.use_degrees=true" in args and "--display_mode=web" in args  # lerobot checks the value
    assert "--robot.port=/dev/x" not in args  # the Hardware page sets it
    assert not any(a.startswith("--gone") for a in args)  # not an option now: kept, not written
    assert m.texts("warn") == [] and actions(m) == []  # and nothing to tidy up


def test_all_options_values_wait_for_the_listing(settings):
    args, m = build(settings, "teleoperate", {"robot.use_degrees": "true"})
    assert "--robot.use_degrees=true" in args
    assert "Checking the extra options against lerobot…" in m.texts("info")
    _, m = build(settings, "teleoperate", {"teleop_time_s": "x"}, listing=EXTRA_LISTING)
    assert errors(m) == ["Duration (s): `x` is not a valid number."]


def test_options_query_follows_the_selected_types(settings):
    from lerobot_gui.commands.extras import options_query

    ctx = context(settings, "rollout", {"strategy.type": "dagger", "gui.leader": "use", "policy.path": LAST})
    command, selections, path = options_query(commands.get_page("rollout"), ctx)  # type: ignore[misc]
    assert command == "lerobot-rollout"
    assert selections == {"robot": "so101_follower", "teleop": "so101_leader", "strategy": "dagger"}
    assert path == str(settings.root / LAST)  # local checkpoints resolve against the workspace


def test_all_options_hides_what_the_page_writes(settings):
    from lerobot_gui.commands.extras import visible_options

    flags_listed = {
        "options": [{"flag": f} for f in ("robot.port", "fps", "resume", "policy.type", "seed", "dataset.root")]
    }
    page = commands.get_page("train")
    shown = [o["flag"] for o in visible_options(page, context(settings, "train"), flags_listed)]
    assert shown == ["fps", "dataset.root"]  # the rest are fields, Hardware or the start mode


# ------------------------------------------------------- hardware (the GUI's own)


def test_hardware_must_be_set(settings):
    _, m = build(settings, "calibrate", hw={"followerPort": ""})
    assert errors(m) == ["Set the follower port."]
    assert actions(m)[0] == {"type": "go", "page": "hardware", "label": "Open Hardware"}
    args, m = build(settings, "calibrate", hw={"followerId": ""})
    assert args == FOLLOWER[:2] and errors(m) == []  # no id: lerobot's default


def test_same_port_for_both_arms_is_an_error(settings):
    _, m = build(settings, "teleoperate", hw={"leaderPort": "/dev/ttyACM0"})
    assert "Follower and leader use the same port." in errors(m)


def test_renumbered_arm_board_is_caught_with_a_fix(settings):
    _, m = build(settings, "teleoperate", hw={"followerPort": "/dev/ttyACM1", "followerBoard": FOLLOWER_BOARD})
    (err,) = [x for x in errors(m) if "board" in x]
    assert "is now `/dev/ttyACM0`, not `/dev/ttyACM1`" in err
    fix = next(a for a in actions(m) if a["type"] == "hardware")
    assert fix["values"]["followerPort"] == "/dev/ttyACM0"


def test_unplugged_board_and_missing_calibration_warn(settings):
    gone = FOLLOWER_BOARD.replace(FOLLOWER_SERIAL, "XXXX")
    _, m = build(settings, "teleoperate", hw={"followerBoard": gone, "followerId": "typo_arm"})
    warns = m.texts("warn")
    assert any("is not plugged in" in w for w in warns)
    assert any("No calibration file for follower id `typo_arm`" in w for w in warns)


def test_camera_checks(settings):
    bad = [{**CAMERAS[0], "name": "top"}, {**CAMERAS[1], "name": "top"}, {**CAMERAS[1], "name": "2nd", "device": ""}]
    _, m = build(settings, "teleoperate", hw={"cameras": bad})
    assert "Camera names must be unique." in errors(m)
    assert "Camera `2nd` has no device." in errors(m)
    # any name is written (quoted): only a name given twice is the GUI's error
    spaced = [{**CAMERAS[0], "name": "top cam"}, {**CAMERAS[1], "name": "1st"}]
    _, m = build(settings, "teleoperate", hw={"cameras": spaced})
    assert errors(m) == []
    _, m = build(settings, "record", hw={"cameras": []})
    assert m.texts("warn") == ["No cameras used yet: run Find cameras and check the ones to use."]


def test_unchecked_cameras_are_kept_but_not_used(settings):
    cams = [{**CAMERAS[0], "use": False}, {**CAMERAS[1], "use": True}, {**CAMERAS[0], "name": "wrist", "use": False}]
    args, m = build(settings, "teleoperate", hw={"cameras": cams})
    assert errors(m) == []  # the unchecked one named wrist too isn't a clash
    assert (
        flags(args)["robot.cameras"]
        == "{wrist: {type: opencv, fps: 30, width: 640, height: 480, index_or_path: /dev/video2}}"
    )
    ctx = context(settings, "teleoperate", hw={"cameras": cams})
    assert hardware.summary(ctx, ["cameras"]) == [{"label": "Cameras", "value": "wrist=video2"}]
    status = [s["text"] for s in hardware.setup_status(context(settings, "hardware", hw={"cameras": cams}))]
    assert "Camera `wrist` on `/dev/video2`." in status and not any("`top`" in t for t in status)
    # none checked: as without cameras
    _, m = build(settings, "record", hw={"cameras": [{**CAMERAS[0], "use": False}]})
    assert m.texts("warn") == ["No cameras used yet: run Find cameras and check the ones to use."]


def test_a_checked_camera_needs_a_name(settings):
    cams = [{"name": "", "type": "opencv", "device": "/dev/video4"}, CAMERAS[1]]
    args, m = build(settings, "teleoperate", hw={"cameras": cams})
    assert errors(m) == ["The camera on `/dev/video4`: give it a name."]
    assert "video4" not in flags(args)["robot.cameras"]
    status = hardware.setup_status(context(settings, "hardware", hw={"cameras": cams}))
    assert {"level": "todo", "text": "The camera on `/dev/video4`: give it a name."}.items() <= next(
        s for s in status if "video4" in s["text"]
    ).items()


def test_cameras_are_not_followed(settings):
    # whatever device a camera has, it is written as it is: no camera is looked for on the machine
    cams = [{**CAMERAS[0], "device": "/dev/video4"}, {**CAMERAS[1], "device": "0"}]
    args, m = build(settings, "teleoperate", hw={"cameras": cams})
    assert errors(m) == [] and not any("camera" in w.lower() for w in m.texts("warn"))
    assert "index_or_path: /dev/video4" in flags(args)["robot.cameras"]
    status = [s["text"] for s in hardware.setup_status(context(settings, "hardware", hw={"cameras": cams}))]
    assert "Camera `top` on `/dev/video4`." in status and "Camera `wrist` on `0`." in status


def test_push_and_trackio_warn_about_logins_only_when_turned_on(settings):
    from lerobot_gui.commands.context import Accounts

    logged_out = Accounts(loaded=True)
    assert build(settings, "record", accounts=logged_out)[1].texts("warn") == []
    _, m = build(settings, "record", {"dataset.push_to_hub": "true"}, accounts=logged_out)
    assert any("needs a Hugging Face login" in w for w in m.texts("warn"))
    _, m = build(settings, "record", {"dataset.push_to_hub": True, "dataset.repo_id": "other/x"}, accounts=LOGGED_IN)
    assert any("needs write access to `other`" in w for w in m.texts("warn"))
    _, m = build(settings, "train", {"trackio.enable": "true"}, accounts=logged_out)
    assert m.texts("warn") == []  # kept on this computer
    _, m = build(settings, "train", {"trackio.enable": "true", "trackio.space_id": "alice/t"}, accounts=logged_out)
    assert any("Trackio Space needs a Hugging Face login" in w for w in m.texts("warn"))
    _, m = build(settings, "train", {"trackio.enable": "true", "trackio.space_id": "alice/t"}, accounts=LOGGED_IN)
    assert m.texts("warn") == []


# ---------------------------------------------------------------- pages


def test_every_page_resolves(settings):
    for page in commands.PAGES:
        out: Any = commands.form(page, context(settings, page.id))
        assert out["page"] == page.id
        if page.exe:
            assert out["command"]["preview"].startswith(f"uv run {page.exe}")


def test_page_list_and_unknown_page():
    ids = [p["id"] for p in commands.page_list()]
    setup = [p["id"] for p in commands.page_list() if p["nav"] == "Setup"]
    assert setup == ["environment", "hardware", "calibrate"] and "rollout" in ids
    with pytest.raises(ValueError):
        commands.get_page("nope")


def test_stored_values_that_are_not_objects_are_dropped(settings):
    ctx = commands.make_context(
        context(settings, "record").snap,
        LOGGED_IN,
        {"record": {"dataset.num_episodes": 7}, "hardware": {"cameras": "garbage"}, "train": "garbage"},
        root=settings.root,
        hf_home=settings.hf_home,
        page="record",
    )
    assert ctx.v == {"dataset.num_episodes": 7}
    assert ctx.hw["cameras"] == [] and "followerPort" not in ctx.hw


# ----------------------------------------------------------- hardware view


def test_hardware_view(settings):
    ctx = context(settings, "hardware", hw={"leaderBoard": LEADER_BOARD})
    view: Any = hardware.view(ctx)
    by_tty = {t["tty"]: t for t in view["ttys"]}
    assert view["roles"] == [{"name": "follower", "label": "Follower"}, {"name": "leader", "label": "Leader"}]
    assert by_tty["/dev/ttyACM0"]["roles"] == ["follower"]
    # its board isn't remembered yet: confirming remembers it, and keeps the arm check
    confirm = by_tty["/dev/ttyACM0"]["confirm"]["follower"]
    assert confirm["values"] == {"followerPort": "/dev/ttyACM0", "followerBoard": FOLLOWER_BOARD}
    assert confirm["keep_check"] is True
    assert by_tty["/dev/ttyACM1"]["confirm"] == {}
    assert by_tty["/dev/ttyACM1"]["serial"] == LEADER_SERIAL
    # the other arm can be put on each tty
    assert list(by_tty["/dev/ttyACM0"]["assign"]) == ["leader"]
    assert list(by_tty["/dev/ttyUSB0"]["assign"]) == ["follower", "leader"]
    assert by_tty["/dev/ttyUSB0"]["board"] is None
    levels = {s["text"].split(" ")[0] + s["level"] for s in view["status"]}
    assert "Leaderok" in levels and "Followerwarn" in levels
    assert view["camera_names"] == ["top", "wrist"]  # what the local runs and datasets saw


def test_putting_an_arm_on_a_port_remembers_its_board(settings):
    from lerobot_gui.adapters.roles import FOLLOWER, LEADER

    ctx = context(settings, "hardware", hw={"followerPort": "/dev/ttyUSB0"})
    action = hardware.assign(ctx, FOLLOWER, "/dev/ttyACM0")
    assert action["values"] == {"followerPort": "/dev/ttyACM0", "followerBoard": FOLLOWER_BOARD}
    assert action.get("toast") == "follower → /dev/ttyACM0" and "keep_check" not in action  # an arm moved
    # a port without a board serial: no board (None removes a remembered one)
    action = hardware.assign(ctx, LEADER, "/dev/ttyUSB0")
    assert action["values"] == {
        "leaderPort": "/dev/ttyUSB0",
        "leaderBoard": None,
        # the follower was there: it gets the leader's port, with its board
        "followerPort": "/dev/ttyACM1",
        "followerBoard": LEADER_BOARD,
    }
    assert action.get("toast") == "Swapped: leader ↔ follower"


def test_a_port_chosen_in_its_field_comes_with_its_board(settings):
    fields = hardware_fields(settings)
    also = fields["leaderPort"]["also"]
    # any name of the port: its tty or its by-id link
    assert also["values"]["/dev/ttyACM1"] == {"leaderBoard": LEADER_BOARD}
    assert also["values"][LEADER_BOARD] == {"leaderBoard": LEADER_BOARD}
    # a port without a board serial, one not plugged in, or none: no board
    assert "/dev/ttyUSB0" not in also["values"] and also["other"] == {"leaderBoard": None}
    assert fields["leaderId"]["also"] is None


def test_following_a_renumbered_board_keeps_it(settings):
    ctx = context(settings, "teleoperate", hw={"followerPort": "/dev/ttyACM1", "followerBoard": FOLLOWER_BOARD})
    assert hardware.follow_patch(ctx) == {"followerPort": "/dev/ttyACM0", "followerBoard": FOLLOWER_BOARD}


def test_no_camera_names_offered_without_runs_or_datasets(settings):
    import dataclasses

    ctx = context(settings, "hardware")
    ctx.snap = dataclasses.replace(ctx.snap, datasets=[], policies=[])
    assert hardware.view(ctx)["camera_names"] == []


def test_hardware_fields(settings):
    fields = hardware_fields(settings)
    labels = [o["label"] for o in fields["followerPort"]["options"]]
    assert f"/dev/ttyACM0  ·  board {FOLLOWER_SERIAL}" in labels and "/dev/ttyUSB0" in labels
    assert [o["value"] for o in fields["followerId"]["options"]] == ["my_follower_arm"]
    assert fields["followerPort"]["flag"] == "--robot.port"
    assert "maxRel" not in fields  # the motion limit is a field of each command page now


SWAPPED: Any = {
    "arms": [
        {
            "role": "follower",
            "port": "/dev/ttyACM0",
            "id": "f",
            "status": "other",
            "detail": "leader l",
            "other_role": "leader",
        },
        {
            "role": "leader",
            "port": "/dev/ttyACM1",
            "id": "l",
            "status": "other",
            "detail": "follower f",
            "other_role": "follower",
        },
    ],
    "swapped": True,
}


def test_arm_guides(settings):
    ctx = context(settings, "hardware")
    view: Any = hardware.view(ctx, SWAPPED)
    guide = view["arm_check"]["arms"][0]["guide"]
    assert guide["level"] == "err" and guide["title"].startswith("NG")
    # each arm on the other's port, with the board on it
    assert guide["actions"][0]["values"] == {
        "followerPort": "/dev/ttyACM1",
        "followerBoard": LEADER_BOARD,
        "leaderPort": "/dev/ttyACM0",
        "leaderBoard": FOLLOWER_BOARD,
    }
    assert guide["actions"][-1] == {
        "type": "set",
        "page": "calibrate",
        "values": {"gui.target": "follower"},
        "label": "Calibrate the follower",
        "go": "calibrate",
    }
    assert any(s["text"].startswith("Arm check, follower: motors hold another arm") for s in view["status"])
    for status in ("ok", "mismatch", "no_file", "error"):
        arm: Any = {"role": "leader", "port": "/dev/ttyACM1", "id": "l", "status": status, "detail": ""}
        assert hardware.arm_guide(ctx, arm, {"arms": [arm], "swapped": False})["text"]


def test_preflight_message_offers_swap_and_run_anyway(settings):
    out = commands.form(commands.get_page("teleoperate"), context(settings, "teleoperate"), preflight=SWAPPED)
    first = out["messages"][0]
    assert first["text"].startswith("Not started: the follower port `ttyACM0`")
    assert [a["type"] for a in first["actions"]] == ["hardware", "go", "go", "run_force"]


# ----------------------------------------------------------------- helpers


@pytest.mark.parametrize(
    ("arg", "shell"),
    [
        ("--robot.port=/dev/ttyACM0", "--robot.port=/dev/ttyACM0"),
        ("--dataset.single_task=pick it up", '--dataset.single_task="pick it up"'),
        ('--task=say "hi"', "--task='say \"hi\"'"),
        ("--x=", "--x=''"),
        ("opencv", "opencv"),
    ],
)
def test_preview_quoting(arg, shell):
    assert domain.quote_arg(arg) == shell


def camera_flag(settings, **hw) -> tuple[str | None, Messages]:
    args, m = build(settings, "teleoperate", hw=hw or None)
    return flags(args).get("robot.cameras"), m


def test_cameras_are_written_with_the_settings_entered_only(settings):
    value, m = camera_flag(settings)
    assert value == (
        "{top: {type: opencv, fps: 30, width: 640, height: 480, index_or_path: /dev/video0, fourcc: MJPG, backend: V4L2}, "
        "wrist: {type: opencv, fps: 30, width: 640, height: 480, index_or_path: /dev/video2}}"
    )
    assert errors(m) == []
    # no settings: only the type and the device (lerobot's defaults for the rest)
    bare = [{"name": "top", "type": "opencv", "device": "/dev/video0"}]
    assert camera_flag(settings, cameras=bare)[0] == "{top: {type: opencv, index_or_path: /dev/video0}}"


def test_camera_settings_of_another_type_are_left_out_and_values_quoted(settings):
    cams = [
        {"name": "top", "type": "opencv", "device": "/dev/video0", "settings": {"color": "x", "fourcc": "MJ: PG"}},
        {"name": "far", "type": "remote", "settings": {"host": "10.0.0.2:5555", "name": "head"}},
        {"name": "top cam: 2", "type": "remote"},
    ]
    value, m = camera_flag(settings, cameras=cams)
    assert value == (
        '{top: {type: opencv, index_or_path: /dev/video0, fourcc: "MJ: PG"}, '
        'far: {type: remote, host: "10.0.0.2:5555", name: head}, '
        '"top cam: 2": {type: remote}}'
    )
    assert errors(m) == []  # a type without a device setting needs no device


def test_a_camera_needs_a_type_lerobot_knows(settings):
    old = [{"name": "top", "device": "/dev/video0", "width": 640}]  # saved before cameras had a type
    value, m = camera_flag(settings, cameras=old)
    assert value == "{}"
    assert errors(m) == ["Camera `top`: choose its type."]
    _, m = camera_flag(settings, cameras=[{"name": "top", "type": "webcam", "device": "/dev/video0"}])
    assert errors(m) == ["Camera `top`: the installed lerobot has no camera type `webcam`."]
    _, m = camera_flag(settings, cameras=[{"name": "top", "type": "opencv"}])
    assert "Camera `top` has no device." in errors(m)


def test_the_hardware_page_and_the_command_pages_check_the_same(settings):
    cams = [
        {"name": "top", "device": "/dev/video0"},  # no type yet
        {"name": "far", "type": "webcam", "device": "/dev/video2"},  # a type the installed lerobot doesn't have
        {"name": "head", "type": "remote"},  # a type without a device setting
        {"name": "side", "type": "opencv"},  # its device setting not set
    ]
    hw = {"followerPort": "/dev/ttyACM7", "followerId": "typo_arm", "leaderPort": "/dev/ttyACM7", "cameras": cams}
    _, m = build(settings, "teleoperate", hw=hw)
    status = {s["text"]: s for s in hardware.setup_status(context(settings, "hardware", hw=hw))}
    # every problem a command page says is a line of the Setup status, in the same words and at the same level
    # (a to-do there: not set yet)
    for msg in m.items:
        assert status[msg.text]["level"] in (msg.level, "todo"), msg.text
    assert {msg.text for msg in m.items} == {
        "Follower port `/dev/ttyACM7` is not plugged in.",
        "Leader port `/dev/ttyACM7` is not plugged in.",
        "No calibration file for follower id `typo_arm` (check the id for typos).",
        "Follower and leader use the same port.",
        "Camera `top`: choose its type.",
        "Camera `far`: the installed lerobot has no camera type `webcam`.",
        "Camera `side` has no device.",
    }
    # Hardware no longer says OK to a camera a command can't write
    assert status["Camera `top`: choose its type."]["level"] == "todo"
    assert status["Camera `far`: the installed lerobot has no camera type `webcam`."]["level"] == "err"
    assert status["Camera `side` has no device."]["level"] == "todo"
    # ...nor asks for a device a type doesn't have
    assert status["Camera `head`."]["level"] == "ok" and not any("head" in x for x in m.texts())
    # where it is fixed: Open Hardware on a command page, the step on the Hardware page
    msg = next(x for x in m.items if x.text == "Camera `top`: choose its type.")
    assert msg.actions == [{"type": "go", "page": "hardware", "label": "Open Hardware"}]
    assert status["Camera `top`: choose its type."]["actions"] == [
        {"type": "scroll", "target": "camsettings-card", "label": "Go to step 4"}
    ]
    assert status["Follower port `/dev/ttyACM7` is not plugged in."]["actions"] == []


def test_hardware_page_advice_stays_on_the_hardware_page(settings):
    _, m = build(settings, "teleoperate")
    assert m.items == []  # boards not recorded, arms not checked: said on the Hardware page only
    status = hardware.setup_status(context(settings, "hardware"))
    todo = next(s for s in status if s["text"].startswith("Arms not checked yet"))
    assert todo["level"] == "todo" and todo["actions"] == [{"type": "check_arms", "label": "Check arms"}]
    assert any("board not recorded yet" in s["text"] for s in status)


def test_hardware_view_offers_lerobots_camera_types_and_settings(settings):
    view: Any = hardware.view(context(settings, "hardware"))
    assert view["camera_types"] == ["opencv", "remote"]
    assert view["camera_device_field"] == {"opencv": "index_or_path", "remote": None}
    fields = {f["key"]: f for f in view["camera_fields"]["opencv"]}
    assert fields["width"]["kind"] == "number" and fields["width"]["default"] is None
    assert fields["rotation"]["kind"] == "choice" and fields["rotation"]["default"] == "NO_ROTATION"
    assert [o["value"] for o in fields["backend"]["options"]] == ["ANY", "V4L2"]
    assert fields["fourcc"]["kind"] == "text"
    assert "new_camera" not in view  # no GUI defaults for a new camera


def test_fields_show_by_lerobots_listing_only(settings):
    # nothing hides the dataset fields of a strategy that doesn't record, or Trackio fields while it is off
    rollout = fields_of(settings, "rollout")
    assert {"dataset.repo_id", "dataset.push_to_hub", "policy.n_action_steps"} <= set(rollout)
    assert "inference.queue_threshold" not in rollout  # a selected type's flags wait for lerobot's listing
    rtc = listing(
        {"flag": "inference.type", "kind": "choice", "choices": ["rtc", "sync"]},
        {"flag": "inference.queue_threshold", "kind": "int"},
    )
    shown = fields_of(settings, "rollout", {"inference.type": "rtc"}, listing=rtc)
    assert "inference.queue_threshold" in shown and "inference.rtc.execution_horizon" not in shown
    train = fields_of(settings, "train", {"gui.mode": "new"})
    assert {"trackio.project", "trackio.space_id", "rename_map"} <= set(train)
    from lerobot_gui.commands.extras import visible_options

    listed = {"options": [{"flag": "dataset.repo_id"}, {"flag": "dataset.video"}, {"flag": "teleop.calibration_dir"}]}
    shown_options = [
        o["flag"] for o in visible_options(commands.get_page("rollout"), context(settings, "rollout"), listed)
    ]
    assert shown_options == ["dataset.video"]  # (dataset.repo_id is a field; the leader's flags are Hardware's)


def test_flag_fields_explain_themselves_with_lerobots_docstring(settings):
    docs = listing(
        {"flag": "fps", "kind": "int", "help": "Limit the maximum frames per second."},
        {"flag": "display_data", "kind": "bool"},
    )
    fields = fields_of(settings, "teleoperate", listing=docs)
    assert fields["fps"]["help"] == "Limit the maximum frames per second."
    assert fields["display_data"]["help"] is None  # lerobot has no docstring: no text of the GUI's own either
    assert fields["gui.cameras"]["help"] == "Pass the cameras named on the Hardware page as `--robot.cameras`."
    pages = {p["id"]: p for p in commands.page_list()}
    assert pages["record"]["desc"] == "Runs `lerobot-record`."
    assert not any("Keys" in h for p in pages.values() for h in p["hints"])


@pytest.mark.parametrize(
    ("value", "key", "written"),
    [
        ("top", True, "top"),
        ("top cam", True, '"top cam"'),
        ("true", True, '"true"'),
        ("null", True, '"null"'),
        ("1", True, '"1"'),
        ("前方", True, '"前方"'),
        ("/dev/video0", False, "/dev/video0"),
        ("NO_ROTATION", False, "NO_ROTATION"),
        ("0", False, "0"),  # a setting that spells a number is that number (an index)
        ("on", False, '"on"'),
        ("MJ: PG", False, '"MJ: PG"'),
        (True, False, "true"),
        (640, False, "640"),
    ],
)
def test_camera_values_are_quoted_unless_yaml_reads_them_back(value, key, written):
    from lerobot_gui.commands.cameras import scalar

    assert scalar(value, key=key) == written


def test_adding_to_a_local_dataset_writes_its_folder_when_left_empty(settings):
    values = {"resume": True, "dataset.repo_id": DATASET}
    args, _ = build(settings, "record", values, hw=HARDWARE)
    assert flags(args)["dataset.root"] == f"lerobot/{DATASET}"  # relative to the workspace, where it runs
    fields = fields_of(settings, "record", values)
    assert fields["dataset.root"]["placeholder"] == f"auto: lerobot/{DATASET}"
    assert fields["dataset.root"]["help"].startswith("Left empty while adding to a local dataset")
    # a folder entered is written as it is; nothing is added otherwise
    args, _ = build(settings, "record", {**values, "dataset.root": "data/x"}, hw=HARDWARE)
    assert flags(args)["dataset.root"] == "data/x" and args.count("--dataset.root=data/x") == 1
    for other in (
        {"dataset.repo_id": DATASET},
        {"resume": True, "dataset.repo_id": "alice/not-here"},
        {"resume": True},
    ):
        assert "dataset.root" not in flags(build(settings, "record", other, hw=HARDWARE)[0])
        assert fields_of(settings, "record", other)["dataset.root"]["placeholder"] == ""
