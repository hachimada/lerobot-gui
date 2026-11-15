"""The Hub's models offered when picking a policy (no network: the listing is faked)."""

import pytest

from lerobot_gui.adapters import hub


@pytest.fixture(autouse=True)
def _empty_cache():
    hub._cache.clear()
    yield
    hub._cache.clear()


def fake(calls):
    def fetch(author, token):
        calls.append((author, token))
        return [{"id": f"{author}/model_{len(calls)}", "downloads": 1, "likes": 0, "created": None, "private": False}]

    return fetch


def test_lerobot_models_anonymously_and_cached():
    calls = []
    first = hub.models(None, fetch=fake(calls))
    assert [g["title"] for g in first["groups"]] == ["lerobot"]
    assert first["groups"][0]["models"][0]["id"] == "lerobot/model_1"
    assert first["error"] is None
    assert hub.models(None, fetch=fake(calls)) == first  # cached
    assert calls == [("lerobot", False)]  # the org is listed without credentials
    hub.models(None, refresh=True, fetch=fake(calls))
    assert len(calls) == 2


def test_the_logged_in_users_models_with_their_token():
    calls = []
    out = hub.models("alice", fetch=fake(calls))
    assert [g["title"] for g in out["groups"]] == ["lerobot", "alice (you)"]
    assert ("alice", None) in calls  # None: the saved token (private models too)


def test_a_failing_listing_keeps_what_was_listed():
    calls = []
    hub.models(None, fetch=fake(calls))

    def broken(author, token):
        raise OSError("offline")

    out = hub.models(None, refresh=True, fetch=broken)
    assert out["error"].startswith("Could not list lerobot's models on the Hub: OSError: offline")
    assert out["groups"][0]["models"][0]["id"] == "lerobot/model_1"
    hub._cache.clear()
    assert hub.models(None, fetch=broken)["groups"][0]["models"] == []


def test_endpoint(client, monkeypatch):
    from lerobot_gui.adapters import accounts

    monkeypatch.setattr(hub, "fetch_models", fake([]))
    monkeypatch.setattr(accounts, "peek", lambda key: {"logged_in": True, "user": "alice"} if key == "hf" else None)
    d = client.get("/api/hub/models").json()
    assert [g["author"] for g in d["groups"]] == ["lerobot", "alice"]
