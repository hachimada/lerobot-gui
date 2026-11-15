"""The devices offered for Train's and Rollout's device: what torch reports on this computer."""

from types import SimpleNamespace
from typing import Any

from lerobot_gui import commands
from lerobot_gui.adapters.torch_devices import read

from .commands_helpers import build, context, flags


def fake_torch(gpus=(), mps=False, xpu=None):
    return SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: bool(gpus), device_count=lambda: len(gpus), get_device_name=lambda i: gpus[i]
        ),
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: mps)),
        **({"xpu": SimpleNamespace(is_available=lambda: xpu)} if xpu is not None else {}),
    )


def test_what_torch_reports():
    assert [d["value"] for d in read(fake_torch())] == ["cpu"]
    one = read(fake_torch(gpus=["RTX A"]))
    assert one[0] == {"value": "cuda", "label": "cuda · RTX A"} and [d["value"] for d in one] == ["cuda", "cpu"]
    two = read(fake_torch(gpus=["RTX A", "RTX B"], mps=False, xpu=True))
    assert [d["value"] for d in two] == ["cuda", "cuda:0", "cuda:1", "xpu", "cpu"]
    assert two[2]["label"] == "cuda:1 · RTX B"
    assert [d["value"] for d in read(fake_torch(mps=True, xpu=False))] == ["mps", "cpu"]


def _device_field(settings, page, key):
    form: Any = commands.form(commands.get_page(page), context(settings, page))
    return next(f for g in form["groups"] for f in g["fields"] if f["key"] == key)


def test_train_and_rollout_offer_this_computers_devices(settings):
    for page, key in (("train", "policy.device"), ("rollout", "device")):
        f = _device_field(settings, page, key)
        assert [(o["value"], o["label"]) for o in f["options"]] == [("cuda", "cuda · Test GPU"), ("cpu", "cpu")]
        assert f["custom"] is True  # another device can be typed
    args, _ = build(settings, "train", {"gui.mode": "new", "policy.type": "act", "policy.device": "cuda:3"})
    assert flags(args)["policy.device"] == "cuda:3"
