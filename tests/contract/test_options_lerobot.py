"""Contract tests: the option listing against the installed lerobot (needs lerobot)."""

import pytest
from pydantic import TypeAdapter

pytest.importorskip("lerobot")
pytestmark = pytest.mark.lerobot

from lerobot_gui.adapters.options import CONFIG_COMMANDS, list_options  # noqa: E402
from lerobot_gui.adapters.roles import FOLLOWER, LEADER, types  # noqa: E402
from lerobot_gui.schemas import OptionsListing  # noqa: E402

SO101 = types(FOLLOWER, LEADER)


def flags(result):
    return {o["flag"]: o for o in result["options"]}


@pytest.mark.parametrize("command", sorted(CONFIG_COMMANDS))
def test_every_command_lists_options(command):
    sel = {"lerobot-train": {"policy": "act"}, "lerobot-calibrate": types(FOLLOWER)}.get(command, SO101)
    result = list_options(command, sel)
    assert result["errors"] == []
    assert len(result["options"]) > 5
    TypeAdapter(OptionsListing).validate_python(result)  # the shape the API declares
    for o in result["options"]:
        assert o["kind"] in {"bool", "int", "float", "str", "json", "enum", "choice"}
        assert not o["flag"].startswith("-")


def test_selected_types_are_expanded_and_others_are_not():
    f = flags(list_options("lerobot-rollout", {**SO101, "strategy": "episodic", "inference": "rtc"}))
    assert f["robot.type"]["selected"] == "so101_follower"
    assert "so101_follower" in f["robot.type"]["choices"]
    assert {"robot.port", "robot.max_relative_target", "robot.cameras"} <= set(f)
    assert {
        "inference.queue_threshold",
        "inference.rtc.execution_horizon",
        "strategy.reset_to_initial_position",
    } <= set(f)
    f_sync = flags(list_options("lerobot-rollout", {**SO101, "strategy": "base", "inference": "sync"}))
    assert "inference.queue_threshold" not in f_sync and "strategy.reset_to_initial_position" not in f_sync


def test_kinds_defaults_and_help():
    f = flags(list_options("lerobot-rollout", {**SO101, "inference": "rtc"}))
    assert f["fps"]["kind"] == "float" and f["fps"]["default"] == "30.0"
    assert f["display_data"]["kind"] == "bool" and f["display_data"]["default"] == "false"
    sched = f["inference.rtc.prefix_attention_schedule"]
    assert sched["kind"] == "enum" and "LINEAR" in sched["choices"]
    assert "foxglove" in f["display_mode"]["help"]  # help text comes from the source comments, like --help


def test_train_trackio_and_preset_flags():
    f = flags(list_options("lerobot-train", {"policy": "act"}))
    assert {
        "trackio.enable",
        "trackio.project",
        "trackio.space_id",
        "trackio.private",
        "use_policy_training_preset",
        "steps",
        "batch_size",
    } <= set(f)
    assert f["policy.type"]["selected"] == "act"
    assert {"policy.chunk_size", "policy.n_action_steps"} <= set(f)
    with_opt = flags(list_options("lerobot-train", {"policy": "act", "optimizer": "adamw"}))
    assert "optimizer.lr" in with_opt


def test_policy_defaults_come_from_the_checkpoint(tmp_path):
    import json

    from lerobot.configs.policies import PreTrainedConfig

    cfg = PreTrainedConfig.get_choice_class("act")(n_action_steps=7, chunk_size=7)
    cfg._save_pretrained(tmp_path)
    assert json.loads((tmp_path / "config.json").read_text())["n_action_steps"] == 7
    f = flags(list_options("lerobot-rollout", {**SO101, "strategy": "base"}, policy_path=str(tmp_path)))
    assert f["policy.type"]["selected"] == "act"
    assert f["policy.n_action_steps"]["default"] == "7"


def test_a_hub_policys_defaults_come_from_its_config_fetched_into_the_cache(tmp_path, monkeypatch):
    """A Hub policy's config is fetched, then read from the Hugging Face cache as lerobot reads it
    (here offline, from a made-up cache that has it)."""
    import huggingface_hub.constants
    from lerobot.configs.policies import PreTrainedConfig

    from ..fakes import make_hub_cache

    saved = tmp_path / "saved"
    saved.mkdir()
    PreTrainedConfig.get_choice_class("act")(n_action_steps=9, chunk_size=9)._save_pretrained(saved)
    cache = make_hub_cache(tmp_path / "hub", [("model", "alice/act-pick", 1)])
    blob = next((cache / "models--alice--act-pick" / "blobs").iterdir())
    blob.write_text((saved / "config.json").read_text())
    monkeypatch.setattr(huggingface_hub.constants, "HF_HUB_CACHE", str(cache))
    monkeypatch.setattr(huggingface_hub.constants, "HF_HUB_OFFLINE", True)
    result = list_options("lerobot-rollout", {**SO101, "strategy": "base"}, policy_path="alice/act-pick")
    assert result["errors"] == []
    assert flags(result)["policy.n_action_steps"]["default"] == "9"


def test_unknown_command():
    with pytest.raises(ValueError):
        list_options("lerobot-find-port")
