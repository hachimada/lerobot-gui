import json
import os
from pathlib import Path

import pytest

from lerobot_gui import workspace
from lerobot_gui.adapters import lerobot_files


def test_datasets(settings):
    found = lerobot_files.datasets(settings)
    by_id = {d["repo_id"]: d for d in found}
    ds = by_id["alice/pick_place_20260105_093000"]
    assert ds["fps"] == 30
    assert ds["episodes"] == 150
    assert ds["cameras"] == ["top", "wrist"]
    assert ds["tasks"] == ["pick up the red cube"]
    assert ds["path"] == "lerobot/alice/pick_place_20260105_093000"  # relative to the workspace


def _run(d):
    """A training run as lerobot-train leaves it: a checkpoint with the policy config."""
    (d / "checkpoints" / "000100" / "pretrained_model").mkdir(parents=True)
    (d / "checkpoints" / "000100" / "pretrained_model" / "config.json").write_text('{"type": "act"}')
    return d


def test_training_runs_are_found_by_their_shape(settings, tmp_path):
    root = settings.root
    _run(root / "my_runs" / "first")  # anywhere in the workspace, not only outputs/train
    _run(root / "a" / "b" / "c" / "d" / "e" / "too_deep")
    _run(root / ".cache" / "hidden")
    _run(root / "venv" / "lib" / "inside")
    (root / "venv" / "pyvenv.cfg").write_text("")
    (root / "outputs" / "loop").symlink_to(root)  # a symlink loop is walked once
    outside = _run(tmp_path / "elsewhere" / "run")
    dirs = {r["dir"] for r in lerobot_files.policies(settings)}
    assert dirs == {"my_runs/first", "outputs/train/2026-01-06/10-15-00_smolvla_pick"}
    # a run the GUI started with --output_dir outside the workspace, or too deep in it
    dirs = {r["dir"] for r in lerobot_files.policies(settings, [outside, Path("a/b/c/d/e/too_deep")])}
    assert {str(outside), "a/b/c/d/e/too_deep"} <= dirs


def test_policies_describe_runs(settings):
    (run,) = lerobot_files.policies(settings)
    assert run["name"] == "10-15-00_smolvla_pick"
    assert run["dir"] == "outputs/train/2026-01-06/10-15-00_smolvla_pick"
    assert run["type"] == "smolvla"
    assert [s["step"] for s in run["steps"]] == ["050000", "010000"]
    assert run["last"].endswith("checkpoints/last/pretrained_model")
    assert run["last_step"] == "050000"
    assert run["cameras"] == ["top", "wrist"]
    assert run["chunk_size"] == 50
    assert run["dataset"] == "alice/pick_place_20260105_093000"
    assert run["train_config"].endswith("last/pretrained_model/train_config.json")
    assert run["steps_total"] == 50000
    assert run["rename_map"] is None  # trained without one


def test_captured_images_map_file_names_to_devices(settings):
    from PIL import Image

    d = settings.root / "outputs" / "captured_images"
    d.mkdir(parents=True)
    for name in ("opencv__dev_video2.png", "opencv__dev_video0.png", "notes.txt", "realsense_123.png"):
        (d / name).write_bytes(b"x")
    Image.new("RGB", (64, 48)).save(d / "opencv__dev_video0.png")
    imgs = workspace.captured_images(settings)
    assert (imgs[0]["width"], imgs[0]["height"]) == (64, 48)  # the frame's size, offered for the camera
    assert (imgs[1]["width"], imgs[1]["height"]) == (None, None)  # not an image
    assert [(i["name"], i["type"], i["device"]) for i in imgs] == [
        ("opencv__dev_video0.png", "opencv", "/dev/video0"),
        ("opencv__dev_video2.png", "opencv", "/dev/video2"),
        ("realsense_123.png", "realsense", "123"),
    ]


def test_capture_dir_must_stay_inside_the_workspace(settings):
    with pytest.raises(ValueError):
        workspace.capture_dir(settings, "../../etc")
    assert workspace.captured_images(settings, "outputs/nothing_here") == []


@pytest.mark.parametrize("name", ["../x.png", ".hidden.png", "a/b.png", "x.txt"])
def test_captured_image_path_rejects_unsafe_names(settings, name):
    with pytest.raises(ValueError):
        workspace.captured_image_path(settings, name)


def test_settings_token_from_the_environment(monkeypatch):
    from lerobot_gui.settings import Settings

    monkeypatch.setenv("LEROBOT_GUI_TOKEN", "dev-token")
    assert Settings.from_env(root="/tmp").token == "dev-token"
    monkeypatch.delenv("LEROBOT_GUI_TOKEN")
    assert len(Settings.from_env(root="/tmp").token) > 20


def test_settings_rel(settings):
    assert settings.rel(settings.root / "a" / "b") == os.path.join("a", "b")
    assert settings.rel(settings.root.parent) == str(settings.root.parent)


def test_mark_older():
    frames = [{"device": d, "mtime": t} for d, t in (("a", 100.0), ("b", 195.0), ("c", 200.0))]
    assert [f["older"] for f in workspace.mark_older(frames, None, 8)] == [True, False, False]
    assert [f["older"] for f in workspace.mark_older(frames, 150.0, 8)] == [True, False, False]
    assert [f["older"] for f in workspace.mark_older(frames, 300.0, 8)] == [True, True, True]  # the last run wrote none
    assert [f["older"] for f in workspace.mark_older(frames, None, None)] == [False, False, False]
    assert workspace.mark_older([], None, 8) == []


def test_names_found_on_disk(settings):
    local = workspace.local_names(lerobot_files.datasets(settings), lerobot_files.policies(settings))
    assert sorted(local["hf_namespaces"]) == ["alice", "bob"]
    assert local["trackio_projects"] == ["pick-demo"]
    assert local["trackio_spaces"] == ["alice/trackio"]


def test_runs_not_logged_to_trackio_name_no_project(settings):
    runs = lerobot_files.policies(settings)
    config = settings.root / runs[0]["train_config"]
    data = json.loads(config.read_text())
    config.write_text(json.dumps({**data, "trackio": {**data["trackio"], "enable": False}}))
    local = workspace.local_names(lerobot_files.datasets(settings), lerobot_files.policies(settings))
    assert local["trackio_projects"] == [] and local["trackio_spaces"] == []
