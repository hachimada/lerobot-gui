"""The argparse reader (the arguments of a script that builds its parser in main()), and the cache
of the listings: a page waiting on the Hub for a policy config holds up no other."""

import argparse
import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor

import pytest

from lerobot_gui.adapters import options


def _script(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    module = types.ModuleType("fake_find_cameras")
    module.argparse = argparse  # type: ignore[attr-defined]
    ran: list[str] = []

    def main() -> None:
        parser = module.argparse.ArgumentParser(description="Find cameras")  # type: ignore[attr-defined]
        parser.add_argument("camera_type", type=str, nargs="?", default=None, choices=["a", "b"], help="Kind.")
        parser.add_argument("--output-dir", type=str, default="out/frames", help="Where   the\n frames go.")
        parser.add_argument("--record-time-s", type=float, default=6.0)
        parser.add_argument("--count", type=int, required=True)
        parser.add_argument("--quiet", action="store_true")
        parser.parse_args()
        ran.append("after parse")  # never reached: nothing of the script runs

    module.main = main  # type: ignore[attr-defined]
    module.ran = ran  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fake_find_cameras", module)
    return module


def test_reads_the_arguments_without_running_the_script(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _script(monkeypatch)
    found = {o["flag"]: o for o in options._argparse_options("fake_find_cameras")}
    assert set(found) == {"camera_type", "output-dir", "record-time-s", "count", "quiet"}
    assert (found["camera_type"]["kind"], found["camera_type"]["choices"]) == ("enum", ["a", "b"])
    assert found["camera_type"]["positional"] and not found["camera_type"]["required"]
    assert found["output-dir"]["default"] == "out/frames"
    assert found["output-dir"]["help"] == "Where the frames go."
    assert (found["record-time-s"]["kind"], found["record-time-s"]["default"]) == ("float", "6.0")
    assert found["count"]["kind"] == "int" and found["count"]["required"]
    assert found["quiet"]["kind"] == "bool"
    assert module.ran == []
    assert module.argparse is argparse  # put back


def test_a_script_without_a_parser_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("fake_no_parser")
    module.argparse = argparse  # type: ignore[attr-defined]
    module.main = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fake_no_parser", module)
    with pytest.raises(ValueError, match="no argument parser"):
        options._argparse_parser("fake_no_parser")
    assert module.argparse is argparse


def test_argparse_commands_are_listed_without_a_config_class(monkeypatch: pytest.MonkeyPatch) -> None:
    _script(monkeypatch)
    monkeypatch.setitem(options.ARGPARSE_COMMANDS, "fake-find", "fake_find_cameras")
    monkeypatch.setattr(options, "_LISTINGS", options._listings())
    listing = options.cached_options("fake-find")
    assert listing is not None and listing["errors"] == []
    assert {o["flag"] for o in listing["options"]} >= {"camera_type", "output-dir"}
    assert options.list_options("fake-find") is listing  # cached


# ------------------------------------------------------------------- the listings kept


@pytest.fixture
def stand_ins(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """list_options with lerobot replaced: fetching `alice/slow` waits until released (like the Hub
    when it can't be reached), a Hub policy in `down` can't be fetched; what is fetched is recorded."""
    release = threading.Event()
    fetched: list[str] = []
    down: set[str] = set()

    def fetch(repo_id: str) -> None:
        fetched.append(repo_id)
        if repo_id == "alice/slow":
            assert release.wait(10)
        if repo_id in down:
            raise OSError("the Hub can't be reached")

    def walk(cls, instance, prefix, selections, instances, out, errors) -> None:
        out.append({"flag": "policy.from", "default": (instances.get("policy") or {}).get("from")})

    monkeypatch.setattr(options, "_config_class", lambda command: object)
    monkeypatch.setattr(options, "_fetch_policy_config", fetch)
    monkeypatch.setattr(options, "_read_policy_config", lambda path, cached_only: {"from": path})
    monkeypatch.setattr(options, "_walk", walk)
    monkeypatch.setattr(options, "_LISTINGS", options._listings())
    return types.SimpleNamespace(release=release, fetched=fetched, down=down)


def _soon(done) -> None:
    deadline = time.monotonic() + 5
    while not done():
        assert time.monotonic() < deadline
        time.sleep(0.01)


def _from(listing: dict) -> str:
    return listing["options"][0]["default"]


def test_a_listing_waiting_on_the_hub_holds_up_no_other(stand_ins, tmp_path) -> None:
    with ThreadPoolExecutor() as pool:
        slow = pool.submit(options.list_options, "lerobot-train", {}, "alice/slow")
        _soon(lambda: stand_ins.fetched == ["alice/slow"])
        # meanwhile: another command, a local checkpoint, another Hub policy (Run reads these too)
        assert options.list_options("lerobot-teleoperate")["errors"] == []
        assert _from(options.list_options("lerobot-rollout", {}, str(tmp_path))) == str(tmp_path)
        assert _from(options.list_options("lerobot-rollout", {}, "alice/fast")) == "alice/fast"
        assert not slow.done()
        stand_ins.release.set()
        assert _from(slow.result(5)) == "alice/slow"


def test_the_same_listing_asked_for_meanwhile_is_built_once(stand_ins) -> None:
    with ThreadPoolExecutor() as pool:
        first = pool.submit(options.list_options, "lerobot-train", {}, "alice/slow")
        _soon(lambda: stand_ins.fetched == ["alice/slow"])
        second = pool.submit(options.list_options, "lerobot-train", {}, "alice/slow")
        assert options.cached_options("lerobot-train", {}, "alice/slow") is None  # still being built
        stand_ins.release.set()
        assert first.result(5) is second.result(5)
    assert stand_ins.fetched == ["alice/slow"]


def test_a_policy_config_that_could_not_be_read_is_read_again_a_minute_later(stand_ins, monkeypatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(options, "_LISTINGS", options._listings(clock=lambda: now[0]))
    stand_ins.down.add("alice/act")
    failed = options.list_options("lerobot-train", {}, "alice/act")
    assert failed["errors"] == ["Could not read the policy config from alice/act: the Hub can't be reached"]
    now[0] += options.RETRY_AFTER_S - 1
    assert options.list_options("lerobot-train", {}, "alice/act") is failed  # kept a while
    stand_ins.down.clear()  # the Hub is back
    now[0] += 2
    assert options.cached_options("lerobot-train", {}, "alice/act") is None  # the page asks again
    again = options.list_options("lerobot-train", {}, "alice/act")
    assert again["errors"] == [] and _from(again) == "alice/act"
    now[0] += 3600
    assert options.list_options("lerobot-train", {}, "alice/act") is again  # a complete one is kept
    assert stand_ins.fetched == ["alice/act", "alice/act"]


def test_a_build_that_fails_is_not_kept(stand_ins, monkeypatch) -> None:
    def broken(command: str) -> type:
        raise ValueError("lerobot changed")

    monkeypatch.setattr(options, "_config_class", broken)
    with pytest.raises(ValueError, match="lerobot changed"):
        options.list_options("lerobot-train")
    monkeypatch.setattr(options, "_config_class", lambda command: object)
    assert options.list_options("lerobot-train")["errors"] == []
