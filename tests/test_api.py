import json

import pytest

from lerobot_gui.app import create_app
from lerobot_gui.jobs import JobManager

from .commands_helpers import HARDWARE
from .conftest import BY_ID, FOLLOWER_SERIAL
from .fakes import arm_result
from .test_jobs import wait_for


def test_page_embeds_the_token(settings, tmp_path):
    from fastapi.testclient import TestClient

    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text('<meta name="lerobot-gui-token" content="__TOKEN__"><script src="/assets/a1.js">')
    (web / "assets" / "a1.js").write_text("console.log(1)")
    app = create_app(settings, web_dir=web)
    with TestClient(app, base_url="http://127.0.0.1:7878") as c:
        r = c.get("/")
        assert r.status_code == 200
        assert f'content="{settings.token}"' in r.text
        assert r.headers["cache-control"] == "no-store"
        asset = c.get("/assets/a1.js")
        assert asset.text == "console.log(1)"
        assert "immutable" in asset.headers["cache-control"]


def test_page_explains_a_missing_build(settings, tmp_path):
    from fastapi.testclient import TestClient

    with TestClient(create_app(settings, web_dir=tmp_path / "none"), base_url="http://127.0.0.1:7878") as c:
        r = c.get("/")
        assert r.status_code == 503 and "npm run build" in r.text


def test_api_needs_the_token(client):
    assert client.get("/api/ports", headers={"X-Token": ""}).status_code == 403
    assert client.get("/api/ports", headers={"X-Token": "wrong"}).status_code == 403
    assert client.get("/api/ports").status_code == 200
    assert client.get("/api/ports?token=test-token", headers={"X-Token": ""}).status_code == 200


def test_other_hosts_are_refused(client):
    # DNS rebinding: a page on evil.example resolving to 127.0.0.1 still sends its own Host header
    assert client.get("/", headers={"Host": "evil.example:7878"}).status_code == 403
    assert client.get("/api/ports", headers={"Host": "evil.example:7878"}).status_code == 403
    assert client.get("/", headers={"Host": "localhost:7878"}).status_code == 200


def test_discover_rescans(client, settings):
    d = client.get("/api/discover").json()
    assert set(d) == {"ports", "calibrations", "datasets", "policies", "local"}
    assert d["local"]["trackio_projects"] == ["pick-demo"]  # names found on disk
    assert [p["tty"] for p in d["ports"]] == ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0"]
    assert (d["datasets"], d["policies"]) == (2, 1)


def test_ports(client):
    d = client.get("/api/ports").json()
    assert set(d) == {"ports", "calibrations"}


def test_captured_images(client, settings):
    d = settings.root / "outputs" / "captured_images"
    d.mkdir(parents=True)
    (d / "opencv__dev_video0.png").write_bytes(b"\x89PNG")
    imgs = client.get("/api/captured-images").json()
    assert [i["device"] for i in imgs] == ["/dev/video0"]
    assert client.get("/api/captured-images/opencv__dev_video0.png").content == b"\x89PNG"
    assert client.get("/api/captured-images/missing.png").status_code == 404
    assert client.get("/api/captured-images/x.txt").status_code == 400
    assert client.get("/api/captured-images", params={"dir": "../.."}).status_code == 400


def _frames(settings, **ages):
    """Frames named like lerobot-find-cameras names them, `age` seconds old."""
    import os
    import time

    d = settings.root / "outputs" / "captured_images"
    d.mkdir(parents=True, exist_ok=True)
    for stem, age in ages.items():
        (d / f"{stem}.png").write_bytes(b"\x89PNG")
        t = time.time() - age
        os.utime(d / f"{stem}.png", (t, t))
    return d


def _older(client, **params):
    return {i["device"]: i["older"] for i in client.get("/api/captured-images", params=params).json()}


def test_frames_an_earlier_run_left_are_marked(client, settings):
    # no run of this GUI: older than the newest frame by more than the capture time (6 s) + 2 s
    _frames(settings, opencv__dev_video0=600, realsense_123=5, opencv__dev_video2=3)
    assert _older(client) == {"/dev/video0": True, "/dev/video2": False, "123": False}
    assert _older(client, record_time="700") == {"/dev/video0": False, "/dev/video2": False, "123": False}
    # after a run (this fake one writes /dev/video0 and /dev/video2): every frame it didn't write, all still listed
    job = client.post("/api/form/find-cameras/run", json={"values": {}}).json()
    assert wait_for(lambda: not _job(client, job["id"])["running"])
    assert _older(client) == {"/dev/video0": False, "/dev/video2": False, "123": True}


def test_a_frame_can_be_deleted(client, settings):
    d = _frames(settings, opencv__dev_video6=3600, opencv__dev_video0=0)
    assert client.delete("/api/captured-images/opencv__dev_video6.png").json() == {"ok": True}
    assert not (d / "opencv__dev_video6.png").exists() and (d / "opencv__dev_video0.png").exists()
    assert client.delete("/api/captured-images/opencv__dev_video6.png").status_code == 404
    for bad in ("notes.txt", ".hidden.png"):
        assert client.delete(f"/api/captured-images/{bad}").status_code == 400
    assert client.delete("/api/captured-images/x.png", params={"dir": "../.."}).status_code == 400


def test_no_frame_is_deleted_while_find_cameras_runs(client, settings):
    import sys

    d = _frames(settings, opencv__dev_video0=0)
    (settings.bin_dir / "lerobot-find-cameras").write_text(f"#!{sys.executable}\nimport time\ntime.sleep(30)\n")
    job = client.post("/api/form/find-cameras/run", json={"values": {}}).json()
    try:
        r = client.delete("/api/captured-images/opencv__dev_video0.png")
        assert r.status_code == 409 and (d / "opencv__dev_video0.png").exists()
    finally:
        client.post(f"/api/jobs/{job['id']}/signal", json={"name": "KILL"})


def _job(client, job_id: str) -> dict:
    return next(j for j in client.get("/api/jobs").json() if j["id"] == job_id)


def _run(client, page: str, values: dict | None = None):
    return client.post(f"/api/form/{page}/run", json={"values": values or {}})


def test_job_lifecycle_over_http(client):
    r = _run(client, "find-port")
    assert r.status_code == 200
    job = r.json()
    assert job["running"] is True and job["hardware"] is True
    assert wait_for(lambda: "press Enter" in "".join(_texts(client, job["id"], until_end=False)))
    assert client.post(f"/api/jobs/{job['id']}/input", json={"text": ""}).json() == {"ok": True}
    events = list(_events(client, job["id"]))
    assert events[0][0] == "info"
    assert events[-1][0] == "end"
    end = events[-1][1]
    assert end["returncode"] == 0 and end["find_port"]["tty"] == "/dev/ttyACM1"
    assert end["phase"] == "reported"
    text = "".join(e[1]["text"] for e in events if e[0] == "message")
    assert "Reconnect the USB cable." in text
    assert [j["id"] for j in client.get("/api/jobs").json()] == [job["id"]]
    assert _job(client, job["id"])["running"] is False


def test_stream_sends_the_info_again_when_the_phase_changes(client):
    job = _run(client, "find-port").json()
    phases = []
    with client.stream("GET", f"/api/jobs/{job['id']}/stream") as r:
        event, sent = "message", False
        for line in r.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
                continue
            if not line.startswith("data: "):
                continue
            data = json.loads(line[6:])
            if event in ("info", "end"):
                phases.append(data["phase"])
            if event == "end":
                break
            if event == "message" and "press Enter" in data["text"] and not sent:
                client.post(f"/api/jobs/{job['id']}/input", json={"text": ""})
                sent = True
            event = "message"
    assert phases[0] in ("scan", "unplug")
    assert "reported" in phases[1:-1]  # re-sent before the end


def test_jobs_start_only_from_a_page(client):
    # no route takes a command line as it is: Run builds it on the server
    assert client.post("/api/jobs", json={"command": "lerobot-find-port", "args": []}).status_code == 405
    assert client.get("/api/jobs/nope").status_code in (404, 405)
    assert _run(client, "no-such-page").status_code == 404


def test_job_errors_map_to_http(client):
    assert client.post("/api/jobs/nope/signal", json={"name": "INT"}).status_code == 404
    r = _run(client, "teleoperate", {"hardware": HARDWARE})
    assert r.status_code == 200, r.text
    try:
        busy = _run(client, "calibrate", {"hardware": HARDWARE})
        assert busy.status_code == 409 and "lerobot-teleoperate" in busy.json()["detail"]
        assert client.post(f"/api/jobs/{r.json()['id']}/signal", json={"name": "HUP"}).status_code == 400
    finally:
        client.post(f"/api/jobs/{r.json()['id']}/signal", json={"name": "KILL"})


def _check_arms_client(settings, statuses: dict[str, str], seen: list):
    from fastapi.testclient import TestClient

    def check(arms):
        seen.append(arms)
        return {"arms": [arm_result(a, statuses[a["role"]]) for a in arms], "swapped": False}

    app = create_app(settings, jobs=JobManager(settings, arm_check=check))
    return TestClient(app, base_url="http://127.0.0.1:7878", headers={"X-Token": settings.token})


def test_check_arms_reads_the_arms_set_on_the_hardware_page(settings):
    seen: list = []
    with _check_arms_client(settings, {"follower": "mismatch"}, seen) as c:
        hardware = {"followerPort": "/dev/ttyACM0", "followerId": "f", "leaderId": "l"}
        r = c.post("/api/check-arms", json={"hardware": hardware}).json()
    assert seen == [[{"role": "follower", "port": "/dev/ttyACM0", "id": "f"}]]  # the leader has no port
    assert r["arms"][0]["status"] == "mismatch"
    assert r["remember"] is None  # not on the right port: nothing to remember


def test_check_arms_remembers_the_boards_of_the_arms_on_the_right_port(settings):
    follower_board = f"/dev/serial/by-id/{BY_ID.format(FOLLOWER_SERIAL)}"
    seen: list = []
    with _check_arms_client(settings, {"follower": "ok", "leader": "ok"}, seen) as c:
        # the follower named by its board's by-id link; the leader on a port without a board serial
        hardware = {"followerPort": follower_board, "followerId": "f", "leaderPort": "/dev/ttyUSB0", "leaderId": "l"}
        remember = c.post("/api/check-arms", json={"hardware": hardware}).json()["remember"]
        assert remember["type"] == "hardware" and remember["keep_check"] is True
        assert remember["values"] == {"followerPort": "/dev/ttyACM0", "followerBoard": follower_board}
        assert remember["toast"] == "Remembered the board of the follower"
        # a board already remembered isn't remembered again
        hardware["followerBoard"] = follower_board
        assert c.post("/api/check-arms", json={"hardware": hardware}).json()["remember"] is None


def test_check_arms_is_refused_while_a_robot_command_runs(settings):
    with _check_arms_client(settings, {"follower": "ok"}, []) as c:
        job = c.post("/api/form/find-port/run", json={"values": {}}).json()
        try:
            hardware = {"followerPort": "/dev/ttyACM0", "followerId": "f"}
            r = c.post("/api/check-arms", json={"hardware": hardware})
            assert r.status_code == 409 and r.json()["detail"] == "lerobot-find-port is using the arms. Stop it first."
        finally:
            c.post(f"/api/jobs/{job['id']}/signal", json={"name": "KILL"})


def test_accounts_actions(client, monkeypatch):
    from lerobot_gui.adapters import accounts

    monkeypatch.setattr(
        accounts, "hf_login", lambda secret: (_ for _ in ()).throw(ValueError("Hugging Face rejected the token"))
    )
    r = client.post("/api/accounts/hf/login", json={"secret": "bad"})
    assert r.status_code == 400 and "rejected" in r.json()["detail"]
    assert client.post("/api/accounts/github/login", json={}).status_code == 404
    monkeypatch.setattr(
        accounts, "hf_logout", lambda: (_ for _ in ()).throw(ValueError("The token comes from the HF_TOKEN variable"))
    )
    r = client.post("/api/accounts/hf/logout", json={})
    assert r.status_code == 400 and "HF_TOKEN" in r.json()["detail"]


def _events(client, job_id):
    with client.stream("GET", f"/api/jobs/{job_id}/stream") as r:
        event = "message"
        for line in r.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                yield event, json.loads(line[6:])
                if event == "end":
                    return
                event = "message"


def _texts(client, job_id, until_end=True):
    """The output so far (the stream is read until its first data chunk when the job still runs)."""
    with client.stream("GET", f"/api/jobs/{job_id}/stream") as r:
        for line in r.iter_lines():
            if line.startswith('data: {"text"'):
                yield json.loads(line[6:])["text"]
                if not until_end:
                    return


@pytest.fixture(autouse=True)
def _kill_leftovers(client):
    yield
    for j in client.get("/api/jobs").json():
        if j["running"]:
            client.post(f"/api/jobs/{j['id']}/signal", json={"name": "KILL"})


def test_training_runs_the_gui_started_are_listed(client, tmp_path):
    run = tmp_path / "elsewhere" / "act"
    (run / "checkpoints" / "000100" / "pretrained_model").mkdir(parents=True)
    (run / "checkpoints" / "000100" / "pretrained_model" / "config.json").write_text('{"type": "act"}')
    client.app.state.ctx.jobs.train_dirs.append(run)  # as when Train ran with --output_dir there
    assert client.get("/api/discover").json()["policies"] == 2
    assert str(run) in [p["dir"] for p in client.app.state.ctx.discovery.snapshot().policies]
