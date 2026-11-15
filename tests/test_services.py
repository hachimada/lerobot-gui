"""The Services page: Hugging Face (local data and its deletion, the account's repos)."""

import pytest

from lerobot_gui.adapters import accounts, environment, hf_local, hub
from lerobot_gui.cache import Cache

from .fakes import make_hub_cache


def repo(repo_id: str, updated: str) -> dict:
    """A repo of the account's, as hub.fetch_repos lists it."""
    return {"id": repo_id, "private": False, "downloads": 0, "likes": 0, "updated": updated, "url": f"/{repo_id}"}


@pytest.fixture
def caches(monkeypatch, tmp_path, settings):
    """lerobot's Hub cache (in HF_LEROBOT_HOME) and huggingface_hub's, with a few repos each."""
    lerobot_cache = make_hub_cache(settings.hf_home / "hub", [("dataset", "lerobot/pusht", 300)])
    hub_cache = make_hub_cache(
        tmp_path / "hf-home" / "hub", [("model", "lerobot/smolvla_base", 1000), ("model", "alice/act-pick", 500)]
    )
    monkeypatch.setattr(
        environment,
        "lerobot_dirs",
        lambda: {"HF_LEROBOT_HOME": settings.hf_home, "HF_LEROBOT_HUB_CACHE": lerobot_cache},
    )
    monkeypatch.setattr(environment, "hub_dirs", lambda: {"HF_HOME": hub_cache.parent, "HF_HUB_CACHE": hub_cache})
    return lerobot_cache, hub_cache


# ---------------------------------------------------------------- local


def test_local_listing(client, settings, caches):
    d = client.get("/api/hf/local").json()
    assert d["home"] == "lerobot"
    datasets = {x["repo_id"]: x for x in d["datasets"]}
    assert set(datasets) == {"alice/pick_place_20260105_093000", "bob/pick-trial"}
    assert datasets["alice/pick_place_20260105_093000"]["size"] > 0
    assert {(c["kind"], c["class"], c["id"]) for c in d["calibrations"]} == {
        ("robots", "so_follower", "my_follower_arm"),
        ("teleoperators", "so_leader", "my_leader_arm"),
    }
    by_name = {c["name"]: c for c in d["caches"]}
    assert [(r["repo_type"], r["repo_id"], r["size"]) for r in by_name["HF_LEROBOT_HUB_CACHE"]["repos"]] == [
        ("dataset", "lerobot/pusht", 300)
    ]
    assert {r["repo_id"] for r in by_name["HF_HUB_CACHE"]["repos"]} == {"lerobot/smolvla_base", "alice/act-pick"}
    assert by_name["HF_HUB_CACHE"]["size"] == 1500


def test_missing_caches_are_empty(client):
    d = client.get("/api/hf/local").json()
    assert [(c["name"], c["repos"], c["error"]) for c in d["caches"]] == [
        ("HF_LEROBOT_HUB_CACHE", [], None),
        ("HF_HUB_CACHE", [], None),
    ]


def test_delete_a_dataset(client, settings, caches):
    r = client.post("/api/hf/local/delete", json={"kind": "dataset", "repo_id": "bob/pick-trial"})
    assert r.status_code == 200, r.text
    assert r.json()["message"].startswith("Deleted the dataset `bob/pick-trial`")
    assert not (settings.hf_home / "bob" / "pick-trial").exists()
    assert {x["repo_id"] for x in r.json()["datasets"]} == {"alice/pick_place_20260105_093000"}


@pytest.mark.parametrize(
    "item",
    [
        {"kind": "dataset", "repo_id": "alice/nothing"},
        {"kind": "dataset", "repo_id": "../../ws"},
        {"kind": "dataset", "repo_id": ""},
        {"kind": "calibration", "calibration_kind": "robots", "cls": "so_follower", "id": "../../x"},
        {"kind": "cache", "cache": "HF_HUB_CACHE", "repo_type": "model", "repo_id": "nobody/nothing"},
        {"kind": "cache", "cache": "/tmp", "repo_type": "model", "repo_id": "alice/act-pick"},
        {"kind": "everything"},
    ],
)
def test_only_listed_items_are_deleted(client, settings, caches, item):
    before = client.get("/api/hf/local").json()
    assert client.post("/api/hf/local/delete", json=item).status_code == 400
    assert client.get("/api/hf/local").json() == before
    assert settings.root.exists()


def test_calibration_files_are_the_ones_in_lerobots_folders(settings, tmp_path):
    import dataclasses

    from .fakes import calibration_folders

    s = dataclasses.replace(settings, calibration=calibration_folders(tmp_path / "calibration-elsewhere"))
    (s.calibration["robots"] / "so_follower").mkdir(parents=True)
    (s.calibration["robots"] / "so_follower" / "alice_follower.json").write_text("{}")
    assert [(c["kind"], c["class"], c["id"]) for c in hf_local.calibration_files(s)] == [
        ("robots", "so_follower", "alice_follower")
    ]
    hf_local.delete(
        s, {"kind": "calibration", "calibration_kind": "robots", "class": "so_follower", "id": "alice_follower"}
    )
    assert hf_local.calibration_files(s) == []
    # the files under HF_LEROBOT_HOME/calibration weren't lerobot's here: untouched
    assert (settings.hf_home / "calibration" / "robots" / "so_follower" / "my_follower_arm.json").exists()


def test_delete_a_calibration_file(client, settings):
    item = {"kind": "calibration", "calibration_kind": "teleoperators", "cls": "so_leader", "id": "my_leader_arm"}
    assert client.post("/api/hf/local/delete", json=item).status_code == 200
    assert not (settings.hf_home / "calibration" / "teleoperators" / "so_leader" / "my_leader_arm.json").exists()
    assert (settings.hf_home / "calibration" / "robots" / "so_follower" / "my_follower_arm.json").exists()


def test_delete_a_cached_repo(client, caches):
    _, hub_cache = caches
    item = {"kind": "cache", "cache": "HF_HUB_CACHE", "repo_type": "model", "repo_id": "alice/act-pick"}
    r = client.post("/api/hf/local/delete", json=item)
    assert r.status_code == 200, r.text
    assert not (hub_cache / "models--alice--act-pick").exists()
    assert (hub_cache / "models--lerobot--smolvla_base").exists()


def test_no_delete_while_a_command_runs(client, settings):
    job = client.post("/api/form/find-port/run", json={"values": {}}).json()
    try:
        r = client.post("/api/hf/local/delete", json={"kind": "dataset", "repo_id": "bob/pick-trial"})
        assert r.status_code == 409 and "lerobot-find-port" in r.json()["detail"]
        assert (settings.hf_home / "bob" / "pick-trial").exists()
    finally:
        client.post(f"/api/jobs/{job['id']}/signal", json={"name": "KILL"})


def test_the_trackio_dashboard_doesnt_hold_a_delete_back(client, settings):
    # it shows Trackio's runs, not lerobot's data
    dashboard = client.app.state.ctx.jobs.start("trackio", ["show"])
    try:
        r = client.post("/api/hf/local/delete", json={"kind": "dataset", "repo_id": "bob/pick-trial"})
        assert r.status_code == 200, r.text
        assert not (settings.hf_home / "bob" / "pick-trial").exists()
    finally:
        dashboard.send_signal("KILL")
        dashboard.wait(5)


def test_size_on_disk(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f").write_bytes(b"12345")
    (tmp_path / "link").symlink_to(tmp_path / "a" / "f")  # not counted twice
    assert hf_local.size_on_disk(tmp_path) == 5 + len(str(tmp_path / "a" / "f"))


# ---------------------------------------------------------------- cloud


@pytest.fixture
def fresh(monkeypatch):
    monkeypatch.setattr(hub, "_cloud_cache", Cache(hub.CLOUD_CACHE_S))


def test_cloud_lists_the_account_and_its_organizations(fresh, monkeypatch, client):
    monkeypatch.setattr(accounts, "peek", lambda key: {"logged_in": True, "user": "alice", "orgs": ["lab"]})
    seen = []

    def fetch(owner):
        seen.append(owner)
        if owner == "lab":
            raise RuntimeError("403 Forbidden")
        return {
            "datasets": [repo("alice/old", "2026-01-01"), repo("alice/new", "2026-03-01")],
            "models": [repo("alice/act-pick", "2026-02-01")],
        }

    monkeypatch.setattr(hub, "fetch_repos", fetch)
    d = client.get("/api/hf/cloud").json()
    assert d["logged_in"] is True
    alice, lab = d["owners"]
    assert (alice["owner"], alice["kind"], lab["owner"], lab["kind"]) == ("alice", "user", "lab", "org")
    assert [x["id"] for x in alice["datasets"]] == ["alice/new", "alice/old"]  # newest first
    assert "403" in lab["error"]
    client.get("/api/hf/cloud")  # cached
    client.get("/api/hf/cloud", params={"refresh": 1})
    assert seen == ["alice", "lab", "lab", "alice", "lab"]  # an error isn't cached


def test_cloud_needs_a_login(monkeypatch, client):
    monkeypatch.setattr(accounts, "peek", lambda key: {"logged_in": False})
    assert client.get("/api/hf/cloud").json() == {"owners": [], "logged_in": False}


def test_the_services_pages(client):
    d = client.get("/api/pages").json()
    services = [p["id"] for p in d["pages"] if p["nav"] == "Services"]
    assert services == ["huggingface", "trackio"] and d["nav"][-1] == "Services"
    assert "accounts" not in [p["id"] for p in d["pages"]]


def test_the_hubs_own_message_is_shown_whole(fresh, monkeypatch, client):
    monkeypatch.setattr(accounts, "peek", lambda key: {"logged_in": True, "user": "alice", "orgs": []})

    class BadRequest(Exception):
        server_message = "Bad request: * Invalid option: expected one of " + '"a"|' * 60 + "\n * at expand[5]"

    def refuse(owner):
        raise BadRequest("400 Client Error")

    monkeypatch.setattr(hub, "fetch_repos", refuse)
    (alice,) = client.get("/api/hf/cloud").json()["owners"]
    assert alice["error"].startswith("Could not list alice's repos on the Hub: BadRequest: Bad request:")
    assert alice["error"].endswith("* at expand[5]")  # where the Hub says the problem is


def test_only_fields_the_hub_takes_are_asked_for():
    # the Hub refuses a listing that asks for `usedStorage` (huggingface_hub's types still name it)
    assert "usedStorage" not in hub._EXPAND
