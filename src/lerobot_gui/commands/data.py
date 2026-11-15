"""Data pages: Teleoperate and Record."""

from __future__ import annotations

from ..adapters.roles import CAMERAS_FLAG, FOLLOWER, LEADER, types
from .common import ARM_CHECK_HINTS, max_rel_field, namespaces
from .context import Context
from .domain import Args, as_bool
from .logins import hf_help, hf_push_checks
from .model import Field, Group, Messages, Option, OptionsQuery, Page, is_set


def local_datasets(ctx: Context) -> list[str]:
    return [d["repo_id"] for d in ctx.snap.datasets]


# ------------------------------------------------------------- teleoperate


def use_cameras(ctx: Context) -> bool:
    return ctx.v.get("gui.cameras") != "none"


TELEOPERATE = Page(
    id="teleoperate",
    title="Teleoperate",
    icon="teleop",
    nav="Data",
    exe="lerobot-teleoperate",
    presets=True,
    desc="Runs `lerobot-teleoperate`.",
    hw=lambda ctx: [FOLLOWER.name, LEADER.name, "cameras" if use_cameras(ctx) else None],
    options=lambda ctx: OptionsQuery(types(FOLLOWER, LEADER)),
    groups=(
        Group(
            "Options",
            (
                Field(
                    "gui.cameras",
                    "Cameras",
                    "choice",
                    flag_label=f"--{CAMERAS_FLAG}",
                    default="use",
                    options=(Option("use", "The cameras named on the Hardware page"), Option("none", "None")),
                    help=f"Pass the cameras named on the Hardware page as `--{CAMERAS_FLAG}`.",
                ),
                max_rel_field(),
                Field("display_data", "Show in Rerun", "bool"),
                Field("fps", "Loop rate (Hz)", "number", half=True, advanced=True),
                Field("teleop_time_s", "Duration (s)", "number", half=True, advanced=True),
            ),
        ),
    ),
    hints=(
        *ARM_CHECK_HINTS,
        "Stop sends Ctrl+C.",
    ),
)

# ------------------------------------------------------------------ record


def _resuming(ctx: Context) -> bool:
    return as_bool(ctx.v.get("resume")) is True


def _repo_suggestions(ctx: Context) -> list[str]:
    return local_datasets(ctx) if _resuming(ctx) else namespaces(ctx)


def _added_to_dir(ctx: Context) -> str | None:
    """The folder of the local dataset being added to, when the Dataset folder is left empty."""
    repo = ctx.v.get("dataset.repo_id")
    if not _resuming(ctx) or is_set(ctx.v.get("dataset.root")) or not is_set(repo) or not ctx.dataset_info(repo):
        return None
    return ctx.dataset_dir(str(repo))


def _record_flags(ctx: Context) -> list[str]:
    """Adding to a local dataset with the Dataset folder empty: that dataset's folder."""
    folder = _added_to_dir(ctx)
    if folder is None:
        return []
    a = Args()
    a.flag("dataset.root", folder)
    return a


def _root_placeholder(ctx: Context) -> str:
    folder = _added_to_dir(ctx)
    return f"auto: {folder}" if folder else ""


def _root_help(ctx: Context) -> str | None:
    if _added_to_dir(ctx) is None:
        return None  # lerobot's own description
    return "Left empty while adding to a local dataset: the folder of that dataset is written."


def _root_suggestions(ctx: Context) -> list[str]:
    repo = ctx.v.get("dataset.repo_id")
    return [ctx.dataset_dir(str(repo))] if is_set(repo) and ctx.dataset_info(repo) else []


def _task_suggestions(ctx: Context) -> list[str]:
    return list((ctx.dataset_info(ctx.v.get("dataset.repo_id")) or {}).get("tasks") or [])


def _record_check(ctx: Context, m: Messages) -> None:
    if as_bool(ctx.v.get("dataset.push_to_hub")) is True:
        hf_push_checks(ctx, m, str(ctx.v.get("dataset.repo_id") or ""))


RECORD = Page(
    id="record",
    title="Record",
    icon="record",
    nav="Data",
    exe="lerobot-record",
    presets=True,
    desc="Runs `lerobot-record`.",
    hw=lambda ctx: [FOLLOWER.name, LEADER.name, "cameras"],
    options=lambda ctx: OptionsQuery(types(FOLLOWER, LEADER)),
    check=_record_check,
    extra_flags=_record_flags,
    handled=("policy.type",),
    groups=(
        Group(
            "Dataset",
            (
                Field("resume", "Add to an existing dataset", "toggle"),
                Field(
                    "dataset.repo_id",
                    "Repo id",
                    "text",
                    mono=True,
                    placeholder="<user>/<name>",
                    suggest=_repo_suggestions,
                    help=hf_help,
                ),
                Field(
                    "dataset.root",
                    "Dataset folder",
                    "text",
                    mono=True,
                    suggest=_root_suggestions,
                    placeholder=_root_placeholder,
                    help=_root_help,
                ),
                Field(
                    "dataset.single_task",
                    "Task",
                    "text",
                    suggest=_task_suggestions,
                ),
                Field("dataset.num_episodes", "Episodes", "number", half=True),
                Field("dataset.episode_time_s", "Episode time (s)", "number", half=True),
                Field("dataset.reset_time_s", "Reset time (s)", "number", half=True),
                Field("dataset.fps", "Dataset fps", "number", half=True, advanced=True),
            ),
        ),
        Group(
            "Options",
            (
                Field("dataset.push_to_hub", "Push to Hub", "bool"),
                max_rel_field(),
                Field("display_data", "Show in Rerun", "bool"),
                Field(
                    "dataset.streaming_encoding",
                    "Streaming encoding",
                    "bool",
                    advanced=True,
                ),
                Field("dataset.encoder_threads", "Encoder threads", "number", half=True, advanced=True),
                Field("play_sounds", "Read events aloud", "bool", advanced=True),
            ),
        ),
    ),
    hints=(*ARM_CHECK_HINTS,),
)
