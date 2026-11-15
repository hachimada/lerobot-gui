"""The Services pages: Hugging Face (its login and data, shown by the frontend) and Trackio's dashboard."""

from __future__ import annotations

from .context import Context
from .model import Field, Group, Page

HUGGINGFACE = Page(
    id="huggingface",
    title="Hugging Face",
    icon="huggingface",
    nav="Services",
    desc=(
        "The Hugging Face login (Push to Hub, private datasets and models), what lerobot and huggingface_hub "
        "keep on this computer, and the datasets and models of the account and its organizations on the Hub."
    ),
)


TRACKIO = Page(
    id="trackio",
    title="Trackio",
    icon="chart",
    nav="Services",
    exe="trackio",
    desc=(
        "Runs `trackio show`: the dashboard of the training runs logged with Trackio (Train: `--trackio.enable`), "
        "in the browser. It runs alongside training."
    ),
    extra_flags=lambda ctx: ["show"],  # the subcommand
    groups=(
        Group(
            "Dashboard",
            (
                Field(
                    "project",
                    "Project",
                    "text",
                    mono=True,
                    suggest=Context.trackio_projects,
                    help="The project the dashboard opens with. The ones offered are those of the training runs here.",
                ),
            ),
        ),
    ),
    hints=("Stop sends Ctrl+C.", "The dashboard's address is in the output."),
)
