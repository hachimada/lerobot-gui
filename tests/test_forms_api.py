"""/api/pages and /api/form/...: the pages over HTTP, and Run building the command on the server."""

import pytest
from fastapi.testclient import TestClient

from lerobot_gui.api.deps import Listings
from lerobot_gui.app import create_app
from lerobot_gui.jobs import JobManager

from .commands_helpers import HARDWARE, flags, option
from .fakes import arm_result
from .test_jobs import swapped_check, wait_for

VALUES = {"hardware": HARDWARE}


def listings(client, **these) -> None:
    """Give the app of `client` these option listings (cached, full) instead of the ones it has."""
    ctx = client.app.state.ctx
    ctx.listings = Listings(**{"cached": ctx.listings.cached, "full": ctx.listings.full, **these})


def test_pages(client):
    d = client.get("/api/pages").json()
    assert d["nav"] == ["Setup", "Data", "Policy", "Services"]
    by_id = {p["id"]: p for p in d["pages"]}
    assert by_id["find-port"]["nav"] is None and by_id["rollout"]["exe"] == "lerobot-rollout"
    assert by_id["teleoperate"]["hints"]
    assert by_id["train"]["hardware"] is False and by_id["record"]["hardware"] is True


def test_form_resolves_fields_command_and_messages(client):
    d = client.post("/api/form/teleoperate", json={"values": {**VALUES, "teleoperate": {"fps": 30}}}).json()
    assert d["page"] == "teleoperate"
    fields = {f["key"]: f for g in d["groups"] for f in g["fields"]}
    assert fields["fps"]["value"] == 30
    assert fields["display_data"]["value"] is None and fields["display_data"]["kind"] == "bool"
    assert flags(d["command"]["args"])["fps"] == "30"
    assert "display_data" not in flags(d["command"]["args"])
    assert d["command"]["preview"].startswith("uv run lerobot-teleoperate \\\n    --robot.type=so101_follower")
    assert [c["label"] for c in d["hardware_summary"]] == ["Follower", "Leader", "Cameras"]
    assert d["errors"] == 0
    assert "hardware_values" not in d  # the browser has them: it sent them
    assert d["options_query"]["selections"] == {"robot": "so101_follower", "teleop": "so101_leader"}


def test_hardware_has_its_own_route(client):
    d = client.post("/api/hardware", json={"hardware": HARDWARE}).json()
    assert [g["title"] for g in d["groups"]] == ["Follower", "Leader"]
    port = d["groups"][0]["fields"][0]
    assert (port["key"], port["flag"], port["value"]) == ("followerPort", "--robot.port", "/dev/ttyACM0")
    assert {t["tty"] for t in d["view"]["ttys"]} == {"/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0"}
    assert d["view"]["arm_check"] is None
    check = {"arms": [arm_result({"role": "follower", "port": "/dev/ttyACM0", "id": "f"}, "ok")], "swapped": False}
    d = client.post("/api/hardware", json={"hardware": HARDWARE, "arm_check": check}).json()
    assert d["view"]["arm_check"]["arms"][0]["guide"]["level"] == "ok"
    # it isn't a command page
    assert client.post("/api/form/hardware", json={"values": VALUES}).status_code == 404


def test_unknown_pages(client):
    assert client.post("/api/form/nope", json={}).status_code == 404
    assert client.post("/api/form/environment", json={}).status_code == 404  # no command
    assert client.post("/api/form/accounts/run", json={}).status_code == 404
    assert client.post("/api/form/find-port/options", json={}).status_code == 404


def test_run_refuses_a_command_with_errors(client):
    r = client.post("/api/form/record/run", json={"values": {**VALUES, "record": {"dataset.num_episodes": "many"}}})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "Episodes: `many` is not a valid number." in detail["message"]
    assert any(m["level"] == "err" for m in detail["messages"])
    assert client.get("/api/jobs").json() == []


def test_run_checks_against_lerobots_listing(client):
    def listing(*_):
        return {
            "options": [{"flag": "dataset.repo_id", "kind": "str", "required": True, "default": None}],
            "errors": [],
        }

    listings(client, full=listing)
    r = client.post("/api/form/train/run", json={"values": VALUES})
    assert r.status_code == 400 and "`--dataset.repo_id`) is required" in r.json()["detail"]["message"]


def test_run_starts_the_built_command(client):
    r = client.post("/api/form/calibrate/run", json={"values": {**VALUES, "calibrate": {"gui.target": "leader"}}})
    assert r.status_code == 200
    job = r.json()
    assert job["page"] == "calibrate" and job["command"] == "lerobot-calibrate"
    assert job["args"] == ["--teleop.type=so101_leader", "--teleop.port=/dev/ttyACM1", "--teleop.id=my_leader_arm"]
    assert wait_for(lambda: not next(j for j in client.get("/api/jobs").json() if j["id"] == job["id"])["running"])


def test_run_with_swapped_arms_then_force(settings):
    app = create_app(settings, jobs=JobManager(settings, arm_check=swapped_check))
    with TestClient(app, base_url="http://127.0.0.1:7878", headers={"X-Token": settings.token}) as c:
        r = c.post("/api/form/teleoperate/run", json={"values": VALUES})
        assert r.status_code == 409
        preflight = r.json()["detail"]["preflight"]
        d = c.post("/api/form/teleoperate", json={"values": VALUES, "preflight": preflight}).json()
        assert d["messages"][0]["text"].startswith("Not started:")
        assert d["messages"][0]["actions"][-1]["type"] == "run_force"
        forced = c.post("/api/form/teleoperate/run", json={"values": VALUES, "force": True})
        assert forced.status_code == 200
        info = forced.json()
        assert info["preflight_notes"][0]["level"] == "err"
        assert info["preflight_notes"][0]["text"].startswith("Arm check, follower: motors hold another arm")
        c.post(f"/api/jobs/{info['id']}/signal", json={"name": "KILL"})


def test_options_listing_is_filtered_for_the_page(client):
    seen = []

    def listing(command, selections, policy_path):
        seen.append((command, selections, policy_path))
        flags = ("robot.port", "robot.use_degrees", "fps")
        return {"options": [option(flag) for flag in flags], "errors": ["x"]}

    listings(client, full=listing)
    d = client.post("/api/form/teleoperate/options", json={"values": VALUES}).json()
    assert [o["flag"] for o in d["options"]] == ["robot.use_degrees"]  # port: Hardware, fps: a field
    assert d["errors"] == ["x"]
    assert seen == [("lerobot-teleoperate", {"robot": "so101_follower", "teleop": "so101_leader"}, None)]


def test_options_listing_errors_are_400(client):
    def boom(*_):
        raise ValueError("No option schema")

    listings(client, full=boom)
    assert client.post("/api/form/teleoperate/options", json={"values": VALUES}).status_code == 400


def test_form_uses_the_cached_listing_only(client):
    def never(*_):
        pytest.fail("the form must not build the listing")

    listings(client, cached=lambda *_: None, full=never)  # not built yet in this process
    extra = {"teleoperate": {"robot.use_degrees": "true"}}
    d = client.post("/api/form/teleoperate", json={"values": {**VALUES, **extra}}).json()
    assert "--robot.use_degrees=true" in d["command"]["args"]
    assert any(m["text"] == "Checking the extra options against lerobot…" for m in d["messages"])


@pytest.fixture(autouse=True)
def _kill_leftovers(client):
    yield
    for j in client.get("/api/jobs").json():
        if j["running"]:
            client.post(f"/api/jobs/{j['id']}/signal", json={"name": "KILL"})
