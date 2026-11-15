import threading

import pytest

from lerobot_gui.cache import Cache


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_kept_for_its_ttl_and_built_again_after_or_on_refresh():
    clock, built = Clock(), []
    cache: Cache[str, int] = Cache(10, clock)

    def build():
        built.append(1)
        return len(built)

    assert cache.get("a", build) == 1
    clock.now = 9
    assert cache.get("a", build) == 1 and cache.fresh("a") == 1
    clock.now = 10
    assert cache.fresh("a") is None and cache.last("a") == 1  # stale, still there
    assert cache.get("a", build) == 2
    assert cache.get("a", build, refresh=True) == 3
    assert cache.get("b", build) == 4  # one value per key


def test_a_failed_build_keeps_nothing_and_the_last_value_stays():
    cache: Cache[str, str] = Cache(None)
    assert cache.get("a", lambda: "old") == "old"

    def fail():
        raise RuntimeError("offline")

    with pytest.raises(RuntimeError):
        cache.get("a", fail, refresh=True)
    assert cache.last("a") == "old" and cache.fresh("a") == "old"
    assert cache.get("a", lambda: "new", refresh=True) == "new"


def test_the_ttl_can_depend_on_the_value():
    clock = Clock()
    cache: Cache[str, tuple[str, bool]] = Cache(lambda v: None if v[1] else 60, clock)
    cache.get("complete", lambda: ("x", True))
    cache.get("partial", lambda: ("y", False))
    clock.now = 1e6
    assert cache.fresh("complete") == ("x", True)  # kept for good
    assert cache.fresh("partial") is None  # built again later


def test_callers_wait_for_the_build_under_way():
    cache: Cache[str, str] = Cache(None)
    started, release, calls = threading.Event(), threading.Event(), []

    def slow():
        calls.append(1)
        started.set()
        release.wait(5)
        return "value"

    results: list[str] = []
    first = threading.Thread(target=lambda: results.append(cache.get("a", slow)))
    first.start()
    assert started.wait(5)
    second = threading.Thread(target=lambda: results.append(cache.get("a", slow)))
    second.start()
    release.set()
    first.join(5)
    second.join(5)
    assert results == ["value", "value"] and len(calls) == 1
