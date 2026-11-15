"""The Rollout page: run a trained policy on the follower, optionally recording (strategies)."""

from __future__ import annotations

import json

from ..adapters.roles import FOLLOWER, LEADER, types
from .common import ARM_CHECK_HINTS, device_options, max_rel_field, namespaces
from .context import Context
from .domain import as_bool, json_map
from .logins import hf_push_checks
from .model import Field, Group, Messages, Option, OptionsQuery, Page
from .policies import local_policies


def strategy(ctx: Context) -> str:
    return str(ctx.v.get("strategy.type") or "")


def uses_leader(ctx: Context) -> bool:
    return ctx.v.get("gui.leader") == "use"


def listing_known(ctx: Context) -> bool:
    """Flags of a selected type (strategy, inference backend) are known from lerobot's listing only."""
    return ctx.listing is not None


def policy_summary(ctx: Context) -> str:
    r = ctx.policy_info(ctx.v.get("policy.path"))
    if not r:
        return "The `pretrained_model` dir of a checkpoint, or a Hub repo id."
    chunk = (
        f"horizon {r['horizon']}" if r.get("horizon") else f"chunk {r['chunk_size']}" if r.get("chunk_size") else None
    )
    parts = [
        r.get("type"),
        chunk,
        f"n_action_steps {r['n_action_steps']}" if r.get("n_action_steps") else None,
        f"cameras {', '.join(r['cameras'])}" if r.get("cameras") else None,
        f"data `{r['dataset']}`" if r.get("dataset") else None,
    ]
    return " · ".join(p for p in parts if p)


def _task_suggestions(ctx: Context) -> list[str]:
    info = ctx.policy_info(ctx.v.get("policy.path")) or {}
    return list((ctx.dataset_info(info.get("dataset")) or {}).get("tasks") or [])


def _trained_rename_map(ctx: Context) -> dict | None:
    """The rename map the selected local policy was trained with (its `train_config.json`)."""
    return (ctx.policy_info(ctx.v.get("policy.path")) or {}).get("rename_map") or None


def _typed_rename_map(ctx: Context) -> object:
    try:
        return json.loads(str(ctx.v.get("rename_map") or ""))
    except ValueError:
        return None


def _rename_suggestions(ctx: Context) -> list[str]:
    trained = _trained_rename_map(ctx)
    return [json.dumps(trained)] if trained and _typed_rename_map(ctx) != trained else []


def _rename_help(ctx: Context) -> str | None:
    if not _trained_rename_map(ctx):
        return None  # lerobot's own words
    if _typed_rename_map(ctx) == _trained_rename_map(ctx):
        return "The rename map this policy was trained with (its `train_config.json`)."
    return "Offered: the rename map this policy was trained with (its `train_config.json`)."


def _options_query(ctx: Context) -> OptionsQuery:
    v = ctx.v
    return OptionsQuery(
        {
            **types(FOLLOWER),
            LEADER.prefix: LEADER.type if uses_leader(ctx) else "",
            "strategy": strategy(ctx),
            "inference": str(v.get("inference.type") or ""),
        },
        policy_path=str(v["policy.path"]) if v.get("policy.path") else None,
    )


def _check(ctx: Context, m: Messages) -> None:
    if as_bool(ctx.v.get("dataset.push_to_hub")) is True:
        hf_push_checks(ctx, m, str(ctx.v.get("dataset.repo_id") or ""))


PAGE = Page(
    id="rollout",
    title="Rollout",
    icon="rollout",
    nav="Policy",
    exe="lerobot-rollout",
    presets=True,
    desc="Runs `lerobot-rollout`.",
    hw=lambda ctx: [FOLLOWER.name, "cameras", LEADER.name if uses_leader(ctx) else None],
    options=_options_query,
    check=_check,
    handled=("policy.type",),
    # the leader's flags come from the Hardware page
    option_filter=lambda flag, ctx: not flag.startswith(LEADER.prefix + "."),
    groups=(
        Group(
            "Policy",
            (
                Field(
                    "policy.path",
                    "Policy",
                    "picker",
                    listed=False,
                    hub=True,
                    mono=True,
                    options=local_policies,
                    help=policy_summary,
                ),
                Field(
                    "rename_map",
                    "Rename map",
                    "text",
                    mono=True,
                    convert=json_map,
                    placeholder='{"observation.images.front": "observation.images.top"}',
                    suggest=_rename_suggestions,
                    help=_rename_help,
                ),
                Field(
                    "task",
                    "Task",
                    "text",
                    suggest=_task_suggestions,
                ),
                Field("duration", "Duration (s)", "number", half=True),
                max_rel_field(),
            ),
        ),
        Group(
            "Inference",
            (
                Field("inference.type", "Backend", "choice", lerobot_choices=True),
                Field(
                    "inference.queue_threshold",
                    "Queue threshold",
                    "number",
                    half=True,
                    show=listing_known,
                ),
                Field(
                    "inference.rtc.execution_horizon",
                    "Execution horizon",
                    "number",
                    half=True,
                    show=listing_known,
                ),
                Field(
                    "inference.rtc.max_guidance_weight",
                    "Max guidance weight",
                    "number",
                    half=True,
                    advanced=True,
                    show=listing_known,
                ),
                Field(
                    "inference.rtc.prefix_attention_schedule",
                    "Prefix schedule",
                    "choice",
                    lerobot_choices=True,
                    half=True,
                    advanced=True,
                    show=listing_known,
                ),
                Field(
                    "policy.n_action_steps",
                    "n_action_steps",
                    "number",
                    half=True,
                    advanced=True,
                ),
            ),
        ),
        Group(
            "Strategy",
            (
                Field(
                    "strategy.type",
                    "Strategy",
                    "choice",
                    lerobot_choices=True,
                ),
                Field(
                    "gui.leader",
                    "Leader arm",
                    "choice",
                    flag_label=f"--{LEADER.prefix}.*",
                    default="none",
                    options=(Option("none", "Not used"), Option("use", "The leader on the Hardware page")),
                    help=f"Pass the leader on the Hardware page as `--{LEADER.prefix}.*`.",
                ),
                Field(
                    "dataset.repo_id",
                    "Dataset repo id",
                    "text",
                    mono=True,
                    placeholder="<user>/<name>",
                    suggest=namespaces,
                ),
                Field("dataset.num_episodes", "Episodes", "number", half=True),
                Field("dataset.episode_time_s", "Episode time (s)", "number", half=True),
                Field("dataset.reset_time_s", "Reset time (s)", "number", half=True),
                Field("strategy.record_autonomous", "Record autonomous frames too", "bool", show=listing_known),
                Field(
                    "strategy.upload_every_n_episodes", "Push every N episodes", "number", half=True, show=listing_known
                ),
                Field("strategy.ring_buffer_seconds", "Ring buffer (s)", "number", half=True, show=listing_known),
                Field("dataset.push_to_hub", "Push to Hub", "bool"),
                Field("dataset.streaming_encoding", "Streaming encoding", "bool", advanced=True),
                Field("dataset.encoder_threads", "Encoder threads", "number", half=True, advanced=True),
            ),
        ),
        Group(
            "Options",
            (
                Field("display_data", "Show in Rerun", "bool"),
                Field("return_to_initial_position", "Return to start pose on exit", "bool"),
                Field("fps", "Control rate (Hz)", "number", half=True, advanced=True),
                Field("device", "Device", "choice", custom=True, options=device_options, half=True, advanced=True),
                Field("interpolation_multiplier", "Interpolation ×", "number", half=True, advanced=True),
                Field("play_sounds", "Read events aloud", "bool", advanced=True),
                Field("use_torch_compile", "torch.compile", "bool", advanced=True),
            ),
        ),
    ),
    hints=("Stop sends Ctrl+C.", *ARM_CHECK_HINTS),
)
