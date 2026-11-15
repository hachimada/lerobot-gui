"""The home dir is shown as `~`; the commands get full paths (no shell expands `~` for them)."""

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from lerobot_gui import commands
from lerobot_gui.adapters import lerobot_files
from lerobot_gui.paths import expand, tilde
from lerobot_gui.settings import Settings

from .commands_helpers import HARDWARE, build, context, flags


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    home = tmp_path / "home" / "alice"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    return home


def test_tilde_and_expand(home):
    assert tilde(home / ".netrc") == "~/.netrc"
    assert tilde(home) == "~"
    assert tilde(str(home) + "2/x") == str(home) + "2/x"  # another dir that starts the same
    assert tilde("/opt/data") == "/opt/data"
    assert expand("~/data/x") == f"{home}/data/x"
    assert expand("~") == str(home)
    assert expand("~bob/x") == "~bob/x" and expand("a/~/b") == "a/~/b" and expand("/x") == "/x"


def test_paths_outside_the_workspace_are_shown_with_tilde(settings, home):
    s = dataclasses.replace(settings, hf_home=home / ".cache" / "lerobot")
    assert s.rel(s.root / "outputs" / "x") == "outputs/x"  # inside: relative, as the commands get it
    assert s.rel(s.hf_home / "alice" / "pick") == "~/.cache/lerobot/alice/pick"
    assert s.rel(Path("/opt/data")) == "/opt/data"


def test_values_with_tilde_reach_the_command_as_full_paths(settings, home):
    args, m = build(settings, "record", {"dataset.repo_id": "alice/x", "dataset.root": "~/data/x"}, hw=HARDWARE)
    assert m.errors == 0
    assert flags(args)["dataset.root"] == f"{home}/data/x"
    page = commands.get_page("record")
    form: Any = commands.form(page, context(settings, "record", {"dataset.root": "~/data/x"}, hw=HARDWARE))
    assert f"--dataset.root={home}/data/x" in form["command"]["preview"]  # the line a shell runs as it is


def test_training_runs_outside_the_workspace_are_offered_with_tilde(settings, home):
    run = home / "runs" / "act"
    (run / "checkpoints" / "000100" / "pretrained_model").mkdir(parents=True)
    (run / "checkpoints" / "000100" / "pretrained_model" / "config.json").write_text('{"type": "act"}')
    (found,) = [r for r in lerobot_files.policies(settings, [run]) if r["name"] == "act"]
    assert found["dir"] == "~/runs/act"
    assert found["last"] == "~/runs/act/checkpoints/000100/pretrained_model"
    ctx = context(settings, "rollout", {"policy.path": found["last"]}, hw=HARDWARE)
    ctx.snap = dataclasses.replace(ctx.snap, policies=[found])
    # the same checkpoint, however its path is written
    for written in (found["last"], f"{run}/checkpoints/000100/pretrained_model/"):
        assert ctx.policy_info(written) is found
    args, _ = commands.build(commands.get_page("rollout"), ctx)
    assert flags(args)["policy.path"] == f"{run}/checkpoints/000100/pretrained_model"


def test_the_data_dirs_and_credentials_are_shown_with_tilde(home, monkeypatch):
    from lerobot_gui.adapters import accounts, environment

    monkeypatch.setattr(environment, "lerobot_dirs", lambda: {"HF_LEROBOT_HOME": home / ".cache" / "lerobot"})
    assert environment.locations()[0]["value"] == "~/.cache/lerobot"
    import huggingface_hub.constants

    token = home / ".cache" / "huggingface" / "token"
    token.parent.mkdir(parents=True)
    token.write_text("hf_saved_secret")
    monkeypatch.setattr(huggingface_hub.constants, "HF_TOKEN_PATH", str(token))
    assert accounts.hf_saved_login() == "~/.cache/huggingface/token"


def test_settings_from_the_environment_keep_full_paths(home):
    assert not str(Settings.from_env(root=str(home)).root).startswith("~")
