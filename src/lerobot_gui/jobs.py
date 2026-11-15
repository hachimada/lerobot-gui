"""Running lerobot commands: one process per job, output kept in memory, stdin and signals forwarded.

Only allowlisted commands run, without a shell, from the GUI's own Python environment, with the
workspace as cwd. Commands that use the robot or the cameras run one at a time; the ones that
drive the follower are checked for swapped arms first.
"""

from __future__ import annotations

import asyncio
import codecs
import contextlib
import os
import signal
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from . import devices, schemas
from .adapters.arms import arm_line
from .adapters.commands import (
    ARM_CHECK_COMMANDS,
    COMMANDS,
    failure_text,
    found_port,
    noted_at_start,
    output_dir,
    output_state,
)
from .paths import tilde
from .settings import Settings

MAX_LOG_CHARS = 2_000_000
MAX_JOBS = 50
#: output the prompt detection looks at
TAIL_CHARS = 20_000
SIGNALS = {"INT": signal.SIGINT, "TERM": signal.SIGTERM, "KILL": signal.SIGKILL}


class JobError(Exception):
    """A request the job runner refuses; `status` is the HTTP status to answer with."""

    status: int
    detail: Any  # a message, or a dict with "message" and more (e.g. the arm check)

    def __init__(self, status: int, detail: Any):
        super().__init__(detail if isinstance(detail, str) else detail.get("message", ""))
        self.status = status
        self.detail = detail


class JobState(TypedDict):
    prompt: schemas.CalibrationPrompt | None
    phase: Literal["scan", "unplug", "reported"] | None


class Job:
    def __init__(
        self,
        s: Settings,
        command: str,
        args: list[str],
        noted: dict[str, str] | None = None,
        page: str | None = None,
    ):
        self.id = uuid.uuid4().hex[:10]
        self.command = command
        #: the GUI page that started it
        self.page = page
        self.args = args
        self.hardware = COMMANDS[command]
        self.started = time.time()
        self.ended: float | None = None
        self.returncode: int | None = None
        self.stop_requested = False
        self.preflight: dict | None = None
        #: what its output is read against, noted as it started (adapters.commands.noted_at_start)
        self.noted = noted or {}
        self._text = ""
        self._base = 0  # log offset of _text[0]
        self._lock = threading.Lock()
        # the environment the GUI was started with, so lerobot resolves its data dir the same way
        env = {**s.env, "PYTHONUNBUFFERED": "1"}
        self.proc = subprocess.Popen(
            [str(s.bin_dir / command), *args],
            cwd=s.root,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # own process group, so signals reach its children too
            bufsize=0,
        )
        self._done = threading.Event()
        threading.Thread(target=self._pump, daemon=True).start()
        threading.Thread(target=self._wait, daemon=True).start()

    # -- output

    def _append(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            self._text += text
            if len(self._text) > MAX_LOG_CHARS:
                drop = len(self._text) - MAX_LOG_CHARS // 2
                self._text = self._text[drop:]
                self._base += drop

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        fd = self.proc.stdout.fileno()
        while True:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            self._append(decoder.decode(chunk))
        self._append(decoder.decode(b"", final=True))

    def _wait(self) -> None:
        self.returncode = self.proc.wait()
        self.ended = time.time()
        self._done.set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._done.wait(timeout)

    @property
    def running(self) -> bool:
        return self.ended is None

    @property
    def end_offset(self) -> int:
        with self._lock:
            return self._base + len(self._text)

    @property
    def text(self) -> str:
        with self._lock:
            return self._text

    def read(self, offset: int) -> tuple[str, int, bool]:
        """Text from `offset`, the new end offset, and whether older text was dropped."""
        with self._lock:
            end = self._base + len(self._text)
            if offset < self._base:
                return self._text, end, True
            return self._text[offset - self._base :], end, False

    # -- control

    def send_input(self, text: str) -> None:
        if not self.running or self.proc.stdin is None:
            raise JobError(409, "The process is not running.")
        try:
            self.proc.stdin.write((text + "\n").encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise JobError(409, f"Could not write to the process: {exc}") from exc

    def send_signal(self, name: str) -> None:
        if name not in SIGNALS:
            raise JobError(400, "name must be INT, TERM or KILL")
        if not self.running:
            return
        self.stop_requested = True
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.proc.pid, SIGNALS[name])

    @property
    def tail(self) -> str:
        with self._lock:
            return self._text[-TAIL_CHARS:]

    def state(self) -> JobState:
        """What the output says right now: lerobot's calibration prompt, Find port's phase."""
        return cast(JobState, output_state(self.command, self.args, self.tail, self.running))

    def info(self) -> schemas.JobInfo:
        notes: list[schemas.Note] = [
            {"level": "err" if a["status"] == "other" else "warn", "text": arm_line(a)}
            for a in (self.preflight or {}).get("arms", [])
            if a["status"] != "ok"
        ]
        return {
            "id": self.id,
            "command": self.command,
            "page": self.page,
            "args": self.args,
            "hardware": self.hardware,
            "started": self.started,
            "ended": self.ended,
            "running": self.running,
            "returncode": self.returncode,
            "stop_requested": self.stop_requested,
            "preflight": cast(schemas.ArmCheck | None, self.preflight),
            "preflight_notes": notes,
            # why it failed (not for a Stop)
            "failure": failure_text(self.command, self.tail, self.returncode)
            if not self.running and self.returncode not in (0, None) and not self.stop_requested
            else None,
            **self.state(),
            "find_port": cast(schemas.FindPortResult | None, found_port(self.command, self.text, self.noted)),
        }


ArmCheck = Callable[[list[dict]], dict]


class JobManager:
    def __init__(self, s: Settings, arm_check: ArmCheck | None = None):
        self.settings = s
        self.jobs: dict[str, Job] = {}
        #: guards `jobs` and `train_dirs`, held only to read or change them
        self._lock = threading.Lock()
        #: held while the robot is taken: by an arm check (it reads the motors over the serial ports) and by the
        #: start of a robot command, so neither begins while the other is under way. The other commands don't wait.
        self._robot_lock = threading.Lock()
        self._arm_check = arm_check
        #: the --output_dir of each training run started here (relative to the workspace or absolute)
        self.train_dirs: list[Path] = []

    def running_hardware_job(self) -> Job | None:
        return next((j for j in self.list() if j.running and j.hardware), None)

    def _read_arms(self, arms: list[dict]) -> dict:
        if self._arm_check is None:
            from .adapters.arms import check_arms

            def default(a: list[dict]) -> dict:
                return check_arms(a, self.settings.calibration)

            self._arm_check = default
        return self._arm_check(arms)

    def check_arms(self, arms: list[dict]) -> dict:
        """Check arms: read the calibration the arms' motors hold. Refused while a robot command runs (it has
        the ports open), and no robot command starts meanwhile."""
        with self._robot_lock:
            busy = self.running_hardware_job()
            if busy:
                raise JobError(409, f"{busy.command} is using the arms. Stop it first.")
            return self._read_arms(arms)

    def start(self, command: str, args: list[str], *, force: bool = False, page: str | None = None) -> Job:
        s = self.settings
        if command not in COMMANDS:
            raise JobError(400, f"Unknown command {command}")
        if not (s.bin_dir / command).exists():
            raise JobError(500, f"{tilde(s.bin_dir / command)} not found")
        if any("\0" in a for a in args):
            raise JobError(400, "Invalid argument")
        hardware = COMMANDS[command]
        with self._robot_lock if hardware else contextlib.nullcontext():
            busy = self.running_hardware_job() if hardware else None
            if busy:
                raise JobError(
                    409,
                    f"{busy.command} is still running. Stop it first (the robot can be used by one command at a time).",
                )
            preflight = None
            if command in ARM_CHECK_COMMANDS:
                from .adapters.arms import arms_from_args

                arms = arms_from_args(args)
                if arms:
                    preflight = self._read_arms(arms)
                    if preflight["swapped"] and not force:
                        raise JobError(
                            409,
                            {
                                "message": "The arms on these ports hold another arm's calibration.",
                                "preflight": preflight,
                            },
                        )
            noted = noted_at_start(command, lambda: devices.ports(s.fs_root))
            job = Job(s, command, args, noted=noted, page=page)
            job.preflight = preflight
            out = output_dir(command, args)
            with self._lock:
                if out and Path(out) not in self.train_dirs:
                    self.train_dirs.append(Path(out))
                self.jobs[job.id] = job
                self._prune()
        return job

    def _prune(self) -> None:
        finished = [j for j in sorted(self.jobs.values(), key=lambda j: j.started) if not j.running]
        for old in finished[: max(0, len(self.jobs) - MAX_JOBS)]:
            self.jobs.pop(old.id, None)

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self.jobs.get(job_id)
        if job is None:
            raise JobError(404, "No such job")
        return job

    def list(self) -> list[Job]:
        with self._lock:
            jobs = list(self.jobs.values())
        return sorted(jobs, key=lambda j: j.started)

    async def shutdown(self, grace_s: float = 8.0) -> None:
        """Ctrl+C every running job (lerobot then returns the arm to its start pose), kill stragglers."""
        running = [j for j in self.list() if j.running]
        for job in running:
            job.send_signal("INT")
        deadline = time.time() + grace_s
        while any(j.running for j in running) and time.time() < deadline:
            await asyncio.sleep(0.2)
        for job in running:
            job.send_signal("KILL")
