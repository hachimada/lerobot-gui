import asyncio
import sys
import threading
import time
from pathlib import Path

import pytest

from lerobot_gui.jobs import MAX_JOBS, JobError, JobManager

from .conftest import BY_ID, FOLLOWER_SERIAL, LEADER_SERIAL
from .fakes import arm_result

TELEOP_ARGS = [
    "--robot.type=so101_follower", "--robot.port=/dev/ttyACM0", "--robot.id=my_follower_arm",
    "--teleop.type=so101_leader", "--teleop.port=/dev/ttyACM1", "--teleop.id=my_leader_arm",
]  # fmt: skip


def wait_for(predicate, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def ok_check(arms):
    return {"arms": [arm_result(a, "ok") for a in arms], "swapped": False}


def swapped_check(arms):
    return {"arms": [arm_result(a, "other", "leader my_leader_arm") for a in arms], "swapped": True}


@pytest.fixture
def jobs(settings):
    manager = JobManager(settings, arm_check=ok_check)
    yield manager
    for job in manager.list():
        if job.running:
            job.send_signal("KILL")
            job.wait(5)


def test_runs_in_the_workspace_and_inherits_the_environment(jobs, settings):
    job = jobs.start("lerobot-train", ["--steps=10"])
    assert job.wait(10)
    assert job.returncode == 0
    assert wait_for(lambda: "cwd=" in job.text)
    assert "train --steps=10" in job.text
    assert f"HF_LEROBOT_HOME={settings.hf_home}" in job.text
    assert f"cwd={settings.root}" in job.text
    info = job.info()
    assert info["running"] is False and info["returncode"] == 0 and info["hardware"] is False


def test_exit_code_is_reported(jobs):
    job = jobs.start("lerobot-record", [])
    assert job.wait(10)
    assert wait_for(lambda: "record" in job.text)
    assert job.info()["returncode"] == 3
    assert job.info()["failure"] == "record"


def test_rejects_unknown_commands_and_nul_bytes(jobs):
    with pytest.raises(JobError) as e:
        jobs.start("bash", ["-c", "id"])
    assert e.value.status == 400
    with pytest.raises(JobError) as e:
        jobs.start("lerobot-train", ["a\0b"])
    assert e.value.status == 400


def test_missing_command_binary(jobs, settings):
    (settings.bin_dir / "lerobot-train").unlink()
    with pytest.raises(JobError) as e:
        jobs.start("lerobot-train", [])
    assert e.value.status == 500


def test_input_reaches_the_process(jobs):
    job = jobs.start("lerobot-find-port", [])
    assert wait_for(lambda: "press Enter" in job.text)
    assert job.info()["find_port"] is None
    job.send_input("")
    assert job.wait(10)
    assert job.returncode == 0
    assert wait_for(lambda: "The port of this MotorsBus" in job.text)


def test_find_port_result_uses_the_by_id_links_from_before_the_unplug(jobs):
    job = jobs.start("lerobot-find-port", [])
    assert job.noted == {
        "/dev/ttyACM0": "/dev/serial/by-id/" + BY_ID.format(FOLLOWER_SERIAL),
        "/dev/ttyACM1": "/dev/serial/by-id/" + BY_ID.format(LEADER_SERIAL),
    }
    assert wait_for(lambda: "press Enter" in job.text)
    job.send_input("")
    assert job.wait(10)
    assert wait_for(lambda: job.info()["find_port"] is not None)
    assert job.info()["find_port"] == {
        "tty": "/dev/ttyACM1",
        "by_id": "/dev/serial/by-id/" + BY_ID.format(LEADER_SERIAL),
    }


def test_stop_sends_ctrl_c_to_the_process_group(jobs):
    job = jobs.start("lerobot-teleoperate", TELEOP_ARGS)
    assert wait_for(lambda: "started" in job.text)
    job.send_signal("INT")
    assert job.wait(10)
    assert job.returncode == 130
    assert job.info()["stop_requested"] is True
    assert wait_for(lambda: "stopped" in job.text)


def test_bad_signal_and_input_after_exit(jobs):
    job = jobs.start("lerobot-rollout", [])
    assert job.wait(10)
    with pytest.raises(JobError) as e:
        job.send_signal("HUP")
    assert e.value.status == 400
    with pytest.raises(JobError) as e:
        job.send_input("x")
    assert e.value.status == 409
    job.send_signal("INT")  # no-op once finished


def test_one_hardware_job_at_a_time_but_training_runs_alongside(jobs):
    teleop = jobs.start("lerobot-teleoperate", TELEOP_ARGS)
    with pytest.raises(JobError) as e:
        jobs.start("lerobot-calibrate", [])
    assert e.value.status == 409 and "lerobot-teleoperate" in str(e.value)
    train = jobs.start("lerobot-train", [])
    assert train.wait(10)
    teleop.send_signal("KILL")
    assert teleop.wait(10)
    calibrate = jobs.start("lerobot-calibrate", [])
    assert calibrate.wait(10)


def test_the_trackio_dashboard_runs_alongside_the_robot_until_stopped(jobs):
    teleop = jobs.start("lerobot-teleoperate", TELEOP_ARGS)
    dashboard = jobs.start("trackio", ["show", "--project=pick"])
    assert dashboard.info()["hardware"] is False
    deadline = time.time() + 10
    while "launched at" not in dashboard.read(0)[0] and time.time() < deadline:
        time.sleep(0.05)
    assert "args show --project=pick" in dashboard.read(0)[0]
    dashboard.send_signal("INT")
    assert dashboard.wait(10) and dashboard.returncode == 0
    teleop.send_signal("KILL")
    assert teleop.wait(10)


def test_no_arm_check_while_a_robot_command_runs(jobs):
    teleop = jobs.start("lerobot-teleoperate", TELEOP_ARGS)
    with pytest.raises(JobError) as e:
        jobs.check_arms([{"role": "follower", "port": "/dev/ttyACM0", "id": "my_follower_arm"}])
    assert e.value.status == 409 and "lerobot-teleoperate" in str(e.value)
    teleop.send_signal("KILL")
    assert teleop.wait(10)


def test_an_arm_check_holds_robot_commands_back_but_not_the_others(settings):
    reading, release = threading.Event(), threading.Event()

    def slow_check(arms):
        reading.set()
        release.wait(10)
        return ok_check(arms)

    jobs = JobManager(settings, arm_check=slow_check)
    arms = [{"role": "follower", "port": "/dev/ttyACM0", "id": "my_follower_arm"}]
    checker = threading.Thread(target=jobs.check_arms, args=(arms,))
    checker.start()
    assert reading.wait(5)
    # the motors are being read: training starts meanwhile...
    assert jobs.start("lerobot-train", []).wait(10)
    # ...a robot command (it would open the same port) waits for the check to end
    started: list = []
    starter = threading.Thread(target=lambda: started.append(jobs.start("lerobot-calibrate", [])))
    starter.start()
    time.sleep(0.3)
    assert started == []
    release.set()
    checker.join(10)
    starter.join(10)
    assert started and started[0].wait(10)


def test_swapped_arms_stop_the_start_unless_forced(settings):
    jobs = JobManager(settings, arm_check=swapped_check)
    with pytest.raises(JobError) as e:
        jobs.start("lerobot-teleoperate", TELEOP_ARGS)
    assert e.value.status == 409
    assert e.value.detail["preflight"]["swapped"] is True
    assert jobs.list() == []
    job = jobs.start("lerobot-teleoperate", TELEOP_ARGS, force=True)
    preflight = job.info()["preflight"]
    assert preflight is not None and preflight["swapped"] is True
    job.send_signal("KILL")
    job.wait(5)


def test_arm_check_only_for_commands_that_drive_the_follower(settings):
    seen = []

    def check(arms):
        seen.append(arms)
        return ok_check(arms)

    jobs = JobManager(settings, arm_check=check)
    jobs.start("lerobot-calibrate", ["--robot.type=so101_follower", "--robot.port=/dev/ttyACM0", "--robot.id=x"]).wait(
        10
    )
    assert seen == []
    job = jobs.start("lerobot-teleoperate", TELEOP_ARGS)
    assert [a["role"] for a in seen[0]] == ["follower", "leader"]
    preflight = job.info()["preflight"]
    assert preflight is not None and preflight["swapped"] is False
    job.send_signal("KILL")
    job.wait(5)


def test_read_returns_new_text_and_offsets(jobs):
    job = jobs.start("lerobot-train", ["x"])
    job.wait(10)
    assert wait_for(lambda: "cwd=" in job.text)
    text, end, reset = job.read(0)
    assert not reset and end == len(text) and text.startswith("train x")
    more, end2, _ = job.read(end)
    assert more == "" and end2 == end


def test_old_finished_jobs_are_pruned(jobs):
    for _ in range(MAX_JOBS + 3):
        jobs.start("lerobot-rollout", []).wait(10)
    assert len(jobs.list()) <= MAX_JOBS + 1


def test_get_unknown_job(jobs):
    with pytest.raises(JobError) as e:
        jobs.get("nope")
    assert e.value.status == 404


def test_shutdown_stops_running_jobs(settings):
    jobs = JobManager(settings, arm_check=ok_check)
    job = jobs.start("lerobot-teleoperate", TELEOP_ARGS)
    assert wait_for(lambda: "started" in job.text)
    asyncio.run(jobs.shutdown(grace_s=5))
    assert job.wait(5) and job.returncode == 130


def test_training_output_dirs_are_remembered(jobs):
    jobs.start("lerobot-train", ["--output_dir=/data/runs/act", "--steps=10"]).wait(5)
    jobs.start("lerobot-train", ["--output_dir=/data/runs/act"]).wait(5)
    jobs.start("lerobot-train", ["--steps=10"]).wait(5)
    assert jobs.train_dirs == [Path("/data/runs/act")]


def test_commands_get_the_environment_the_gui_was_started_with(jobs, settings, monkeypatch):
    # a library the GUI uses may set variables in the GUI's environment while it runs (such as the
    # address of a service it started); a command must not inherit them
    monkeypatch.setenv("SET_FOR_THE_GUI", "2-12345-unix-/tmp/gui-service")
    script = settings.bin_dir / "lerobot-train"
    script.write_text(
        f"#!{sys.executable}\nimport os\n"
        "print('service', os.environ.get('SET_FOR_THE_GUI'), 'home', os.environ.get('HF_LEROBOT_HOME'))\n"
    )
    job = jobs.start("lerobot-train", [])
    assert job.wait(5)
    assert f"service None home {settings.hf_home}" in job.text
