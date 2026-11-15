"""Presets: a command page's values saved under a name, in the GUI's settings dir."""

import json

import pytest

TRAIN = {"gui.mode": "finetune", "policy.path": "lerobot/smolvla_base", "steps": 20000, "dataset.repo_id": "alice/pick"}


def test_save_list_load_delete(client, settings):
    assert client.get("/api/presets/train").json() == []
    saved = client.put("/api/presets/train/smolvla pick", json={"values": {**TRAIN, "batch_size": ""}}).json()
    assert saved["name"] == "smolvla pick" and saved["values"] == TRAIN  # empty values aren't kept
    path = settings.config_dir / "presets" / "train" / "smolvla pick.json"
    assert json.loads(path.read_text())["values"] == TRAIN  # a file that can be read and edited
    assert [(p["name"], p["count"]) for p in client.get("/api/presets/train").json()] == [("smolvla pick", 4)]
    assert client.get("/api/presets/train/smolvla pick").json()["values"] == TRAIN
    # saving under the same name replaces it
    client.put("/api/presets/train/smolvla pick", json={"values": {"steps": 5}})
    assert client.get("/api/presets/train/smolvla pick").json()["values"] == {"steps": 5}
    assert client.delete("/api/presets/train/smolvla pick").json() == []
    assert not path.exists()


def test_presets_are_per_page(client):
    client.put("/api/presets/teleoperate/slow", json={"values": {"fps": 15}})
    client.put("/api/presets/train/slow", json={"values": {"steps": 1}})
    assert client.get("/api/presets/teleoperate/slow").json()["values"] == {"fps": 15}
    assert client.get("/api/presets/train/slow").json()["values"] == {"steps": 1}


@pytest.mark.parametrize("page", ["hardware", "environment", "huggingface", "find-port", "trackio", "nope"])
def test_only_the_command_pages_have_presets(client, page):
    assert client.get(f"/api/presets/{page}").status_code == 404
    assert client.put(f"/api/presets/{page}/x", json={"values": {}}).status_code == 404


def test_the_pages_say_which_have_presets(client):
    # the same pages as the API takes: the frontend shows the Presets card by it
    pages = client.get("/api/pages").json()["pages"]
    assert {p["id"] for p in pages if p["presets"]} == {"calibrate", "teleoperate", "record", "train", "rollout"}


@pytest.mark.parametrize("name", [".hidden", "a\\b", " ", "x" * 81])
def test_names_that_are_refused(client, settings, name):
    r = client.put(f"/api/presets/train/{name}", json={"values": {"steps": 1}})
    assert r.status_code == 400 and "preset name" in r.json()["detail"]
    assert not (settings.config_dir / "presets" / "train").exists() or not any(
        (settings.config_dir / "presets" / "train").iterdir()
    )


def test_a_slash_in_the_name_never_reaches_another_folder(client, settings):
    assert client.put("/api/presets/train/..%2F..%2Fescape", json={"values": {}}).status_code in (400, 404)
    assert not (settings.config_dir / "escape.json").exists()


def test_missing_and_broken_presets(client, settings):
    assert client.get("/api/presets/train/nothing").status_code == 404
    assert client.delete("/api/presets/train/nothing").status_code == 404
    folder = settings.config_dir / "presets" / "train"
    folder.mkdir(parents=True)
    (folder / "broken.json").write_text("{not json")
    assert client.get("/api/presets/train").json() == []  # skipped, not an error
    assert client.get("/api/presets/train/broken").status_code == 404


def test_the_settings_dir_is_xdg_or_dot_config(monkeypatch, tmp_path):
    from lerobot_gui.settings import default_config_dir

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert default_config_dir() == tmp_path / "xdg" / "lerobot-gui"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert default_config_dir() == tmp_path / "home" / ".config" / "lerobot-gui"
