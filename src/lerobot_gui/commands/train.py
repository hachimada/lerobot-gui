"""The Train page: a new policy, fine-tuning a pretrained one, or resuming a run."""

from __future__ import annotations

from .common import device_options, namespaces
from .context import Context
from .domain import as_bool, episode_list, fmt_step, json_map
from .logins import hf_help, hf_push_checks, trackio_checks
from .model import Field, Group, Messages, Option, OptionGroup, OptionsQuery, Page, is_set
from .policies import local_policies, run_label

MODE_HELP = {
    "new": "Writes `--policy.type`.",
    "finetune": "Writes `--policy.path`: a model on the Hub or a local checkpoint.",
    "resume": "Writes `--resume=true` and `--config_path`.",
}


def mode(ctx: Context) -> str:
    return str(ctx.v.get("gui.mode") or "finetune")


def _resume_options(ctx: Context) -> list[Option | OptionGroup]:
    return [
        Option(
            r["train_config"],
            f"{r['dir']} · {run_label(r)} · step {fmt_step(r['last_step'])} of "
            f"{fmt_step(str(r.get('steps_total') or '?'))}",
        )
        for r in ctx.snap.policies
        if r.get("train_config")
    ]


def _dataset_options(ctx: Context) -> list[Option | OptionGroup]:
    return [Option(d["repo_id"], f"{d['repo_id']}  ·  {d['episodes']} ep · {d['fps']} fps") for d in ctx.snap.datasets]


def _options_query(ctx: Context) -> OptionsQuery:
    v = ctx.v
    if mode(ctx) == "new":
        return OptionsQuery({"policy": str(v.get("policy.type") or "")})
    if mode(ctx) == "finetune":
        return OptionsQuery(policy_path=str(v["policy.path"]) if is_set(v.get("policy.path")) else None)
    config = str(v.get("config_path") or "")
    return OptionsQuery(policy_path=config.rsplit("/", 1)[0] if config else None)


def _check(ctx: Context, m: Messages) -> None:
    if mode(ctx) == "resume":
        return
    if as_bool(ctx.v.get("policy.push_to_hub")) is True:
        hf_push_checks(ctx, m, str(ctx.v.get("policy.repo_id") or ""))
    if as_bool(ctx.v.get("trackio.enable")) is True:
        trackio_checks(ctx, m)


def _mode_is(*modes: str):
    return lambda ctx: mode(ctx) in modes


def _not_resume(ctx: Context) -> bool:
    return mode(ctx) != "resume"


PAGE = Page(
    id="train",
    title="Train",
    icon="train",
    nav="Policy",
    exe="lerobot-train",
    presets=True,
    desc="Runs `lerobot-train`.",
    options=_options_query,
    # resuming means --resume=true with the run's config
    extra_flags=lambda ctx: ["--resume=true"] if mode(ctx) == "resume" else [],
    check=_check,
    handled=("resume", "policy.type", "policy.path", "config_path"),
    groups=(
        Group(
            "Policy",
            (
                Field(
                    "gui.mode",
                    "Start from",
                    "seg",
                    default="finetune",
                    help=lambda ctx: MODE_HELP.get(mode(ctx)),
                    options=(Option("new", "New policy"), Option("finetune", "Pretrained"), Option("resume", "Resume")),
                ),
                Field("policy.type", "Policy type", "choice", lerobot_choices=True, show=_mode_is("new")),
                Field(
                    "policy.path",
                    "Pretrained policy",
                    "picker",
                    listed=False,
                    hub=True,
                    mono=True,
                    show=_mode_is("finetune"),
                    options=local_policies,
                ),
                Field(
                    "config_path",
                    "Run to resume",
                    "choice",
                    listed=False,
                    custom=True,
                    mono=True,
                    show=_mode_is("resume"),
                    options=_resume_options,
                ),
                Field("steps", "Total steps", "number", show=_mode_is("resume")),
            ),
        ),
        Group(
            "Dataset",
            (
                Field(
                    "dataset.repo_id",
                    "Dataset",
                    "choice",
                    custom=True,
                    mono=True,
                    options=_dataset_options,
                ),
                Field(
                    "rename_map",
                    "Rename map",
                    "text",
                    mono=True,
                    convert=json_map,
                    placeholder='{"observation.images.top": "observation.images.camera1"}',
                ),
                Field(
                    "dataset.episodes",
                    "Episodes",
                    "text",
                    mono=True,
                    advanced=True,
                    convert=episode_list,
                    placeholder="e.g. 0-39 or 0,1,2",
                ),
                Field(
                    "dataset.image_transforms.enable",
                    "Image augmentation",
                    "bool",
                    advanced=True,
                ),
                Field(
                    "dataset.eval_split",
                    "Eval split",
                    "number",
                    half=True,
                    advanced=True,
                ),
                Field("eval_steps", "Eval every N steps", "number", half=True, advanced=True),
            ),
            show=_not_resume,
        ),
        Group(
            "Training",
            (
                Field("steps", "Steps", "number", half=True),
                Field("batch_size", "Batch size", "number", half=True),
                Field(
                    "num_workers",
                    "Dataloader workers",
                    "number",
                    half=True,
                ),
                Field("save_freq", "Save every", "number", half=True),
                Field("policy.optimizer_lr", "Learning rate", "number", half=True, advanced=True),
                Field("policy.n_action_steps", "n_action_steps", "number", half=True, advanced=True),
                Field("log_freq", "Log every", "number", half=True, advanced=True),
                Field("seed", "Seed", "number", half=True, advanced=True),
                Field(
                    "policy.device", "Device", "choice", custom=True, options=device_options, half=True, advanced=True
                ),
                Field("policy.use_amp", "Mixed precision", "bool", advanced=True),
            ),
            show=_not_resume,
        ),
        Group(
            "Output",
            (
                Field("output_dir", "Output dir", "text", mono=True),
                Field("job_name", "Job name", "text", mono=True, half=True, advanced=True),
                Field("policy.push_to_hub", "Push to Hub", "bool"),
                Field(
                    "policy.repo_id",
                    "Model repo id",
                    "text",
                    mono=True,
                    placeholder="<user>/<model>",
                    suggest=namespaces,
                    help=hf_help,
                ),
                Field(
                    "trackio.enable",
                    "Trackio",
                    "bool",
                    help="The [Trackio](#trackio) page opens the dashboard of the runs logged.",
                ),
                Field(
                    "trackio.project",
                    "Trackio project",
                    "text",
                    mono=True,
                    half=True,
                    suggest=Context.trackio_projects,
                ),
                Field(
                    "trackio.space_id",
                    "Trackio Space",
                    "text",
                    mono=True,
                    half=True,
                    placeholder="<user>/<space>",
                    suggest=Context.trackio_spaces,
                    help=hf_help,
                ),
                Field(
                    "trackio.private",
                    "Private Space",
                    "bool",
                ),
            ),
            show=_not_resume,
        ),
    ),
    hints=(
        "Training can run next to a robot command; only one robot command runs at a time.",
        "Stop sends Ctrl+C.",
    ),
)
