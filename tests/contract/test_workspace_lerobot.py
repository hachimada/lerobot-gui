"""What the GUI reads of lerobot's data, against the installed lerobot.

A dataset and a training run are written with lerobot's own code (as lerobot-record and
lerobot-train write them), then read back with the GUI's readers.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("lerobot")
pytestmark = pytest.mark.lerobot

from lerobot_gui import workspace  # noqa: E402
from lerobot_gui.adapters import lerobot_files  # noqa: E402
from lerobot_gui.settings import Settings  # noqa: E402

from ..fakes import calibration_folders  # noqa: E402

TASK = "pick up the red cube"
JOINTS = ["shoulder_pan.pos", "gripper.pos"]
FEATURES = {
    "observation.images.top": {"dtype": "image", "shape": (6, 8, 3), "names": ["height", "width", "channels"]},
    "observation.state": {"dtype": "float32", "shape": (2,), "names": JOINTS},
    "action": {"dtype": "float32", "shape": (2,), "names": JOINTS},
}


@pytest.fixture
def lerobot_settings(tmp_path: Path) -> Settings:
    root, home = tmp_path / "workspace", tmp_path / "lerobot-home"
    root.mkdir()
    home.mkdir()
    return Settings(
        root=root,
        hf_home=home,
        calibration=calibration_folders(home / "calibration"),
        bin_dir=tmp_path,
        fs_root=tmp_path,
        port=7878,
        token="t",
    )


def _dataset(s: Settings):
    """alice/pick-demo, recorded with two episodes of three frames."""
    from lerobot.datasets.lerobot_dataset import LeRobotDataset

    ds = LeRobotDataset.create(
        "alice/pick-demo", fps=30, features=FEATURES, root=s.hf_home / "alice" / "pick-demo",
        robot_type="so101_follower", use_videos=False,
    )  # fmt: skip
    for _ in range(2):
        for _ in range(3):
            ds.add_frame(
                {
                    "observation.images.top": np.zeros((6, 8, 3), dtype=np.uint8),
                    "observation.state": np.zeros(2, dtype=np.float32),
                    "action": np.zeros(2, dtype=np.float32),
                    "task": TASK,
                }
            )
        ds.save_episode()
    ds.finalize()
    return ds


class _Policy:
    """Stands in for the model: writes lerobot's config.json of the policy, not the weights."""

    def __init__(self, config) -> None:
        self.config = config

    def save_pretrained(self, directory: Path, state_dict=None) -> None:
        self.config.save_pretrained(directory)


def _training_run(s: Settings, ds) -> Path:
    """A lerobot-train run of ACT on the dataset, with checkpoints at steps 1000 and 2000."""
    from lerobot.common.train_utils import get_step_checkpoint_dir, save_checkpoint, update_last_checkpoint
    from lerobot.configs.default import DatasetConfig, TrackioConfig
    from lerobot.configs.train import TrainPipelineConfig
    from lerobot.configs.types import FeatureType
    from lerobot.policies.act.configuration_act import ACTConfig
    from lerobot.utils.feature_utils import dataset_to_policy_features

    policy = ACTConfig(
        chunk_size=20, n_action_steps=20, device="cpu", push_to_hub=False, repo_id="bob/act-pick",
        pretrained_backbone_weights=None,
    )  # fmt: skip
    # as lerobot's make_policy sets them from the dataset
    features = dataset_to_policy_features(ds.meta.features)
    policy.output_features = {k: f for k, f in features.items() if f.type is FeatureType.ACTION}
    policy.input_features = {k: f for k, f in features.items() if k not in policy.output_features}
    output_dir = s.root / "outputs" / "train" / "pick_act"
    cfg = TrainPipelineConfig(
        dataset=DatasetConfig(repo_id="alice/pick-demo"), policy=policy, output_dir=output_dir, steps=2000,
        trackio=TrackioConfig(enable=True, project="pick", space_id="alice/trackio"),
        rename_map={"observation.images.front": "observation.images.top"},
    )  # fmt: skip
    for step in (1000, 2000):
        checkpoint = get_step_checkpoint_dir(output_dir, cfg.steps, step)
        save_checkpoint(checkpoint, step, cfg, _Policy(policy), optimizer=None)  # type: ignore[arg-type]
        update_last_checkpoint(checkpoint)
    return output_dir


def test_datasets_read_what_lerobot_writes(lerobot_settings):
    _dataset(lerobot_settings)
    [found] = lerobot_files.datasets(lerobot_settings)
    assert {k: found[k] for k in ("repo_id", "fps", "episodes", "frames", "robot_type", "cameras", "tasks")} == {
        "repo_id": "alice/pick-demo",
        "fps": 30,
        "episodes": 2,
        "frames": 6,
        "robot_type": "so101_follower",
        "cameras": ["top"],
        "tasks": [TASK],
    }


def test_training_runs_read_what_lerobot_writes(lerobot_settings):
    run = _training_run(lerobot_settings, _dataset(lerobot_settings))
    [found] = lerobot_files.policies(lerobot_settings)
    checkpoints = run.relative_to(lerobot_settings.root) / "checkpoints"
    assert {k: v for k, v in found.items() if k != "mtime"} == {
        "name": "pick_act",
        "dir": "outputs/train/pick_act",
        "type": "act",
        "steps": [
            {"step": "002000", "path": str(checkpoints / "002000" / "pretrained_model")},
            {"step": "001000", "path": str(checkpoints / "001000" / "pretrained_model")},
        ],
        "last": str(checkpoints / "last" / "pretrained_model"),
        "last_step": "002000",
        "train_config": str(checkpoints / "last" / "pretrained_model" / "train_config.json"),
        "cameras": ["top"],
        "chunk_size": 20,
        "horizon": None,
        "n_action_steps": 20,
        "dataset": "alice/pick-demo",
        "rename_map": {"observation.images.front": "observation.images.top"},
        "steps_total": 2000,
        "repo_id": "bob/act-pick",
        "trackio_project": "pick",
        "trackio_space": "alice/trackio",
    }


def test_names_found_on_disk(lerobot_settings):
    _training_run(lerobot_settings, _dataset(lerobot_settings))
    s = lerobot_settings
    found = workspace.local_names(lerobot_files.datasets(s), lerobot_files.policies(s))
    assert found["hf_namespaces"] == ["alice", "bob"]
    assert (found["trackio_projects"], found["trackio_spaces"]) == (["pick"], ["alice/trackio"])


def test_data_dir_is_lerobots():
    from lerobot.utils.constants import HF_LEROBOT_HOME

    assert Settings.from_env(root="/tmp").hf_home == HF_LEROBOT_HOME


def test_the_environment_page_shows_lerobots_own_dirs():
    from huggingface_hub import constants as hub
    from lerobot.utils import constants

    from lerobot_gui.adapters.environment import locations
    from lerobot_gui.paths import tilde

    found = {loc["name"]: loc["value"] for loc in locations()}
    assert found == {
        "HF_LEROBOT_HOME": tilde(constants.HF_LEROBOT_HOME),
        "HF_LEROBOT_CALIBRATION": tilde(constants.HF_LEROBOT_CALIBRATION),
        "HF_LEROBOT_HUB_CACHE": tilde(constants.HF_LEROBOT_HUB_CACHE),
        "HF_HOME": tilde(hub.HF_HOME),
        "HF_HUB_CACHE": tilde(hub.HF_HUB_CACHE),
    }
