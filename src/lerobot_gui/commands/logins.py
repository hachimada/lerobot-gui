"""Checks and help texts about the Hugging Face login used by Push to Hub and Trackio Spaces."""

from __future__ import annotations

from .context import Context
from .model import OPEN_HF, Messages, is_set


def hf_push_checks(ctx: Context, m: Messages, repo: str) -> None:
    a = ctx.accounts
    if not a.loaded:
        return
    hf = a.hf
    if not hf.get("logged_in"):
        error = f" ({hf['error']})" if hf.get("error") else ""
        m.warn(f"Push to Hub needs a Hugging Face login{error}.", OPEN_HF)
        return
    ns = str(repo or "").split("/")[0]
    mine = [x for x in [hf.get("user"), *(hf.get("orgs") or [])] if x]
    if ns and hf.get("user") and ns not in mine:
        m.warn(f"You are logged in as `{hf['user']}`; pushing to `{ns}/…` needs write access to `{ns}`.")
    if hf.get("token_role") == "read":
        m.warn("The saved Hugging Face token is read-only: pushing needs a token with write access.", OPEN_HF)


def trackio_checks(ctx: Context, m: Messages) -> None:
    """A Trackio Space is on the Hub: logging to one needs the Hugging Face login."""
    a = ctx.accounts
    if a.loaded and is_set(ctx.v.get("trackio.space_id")) and not a.hf.get("logged_in"):
        error = f" ({a.hf['error']})" if a.hf.get("error") else ""
        m.warn(f"Logging to a Trackio Space needs a Hugging Face login{error}.", OPEN_HF)


def hf_help(ctx: Context) -> str:
    a = ctx.accounts
    if not a.loaded:
        return "Checking the Hugging Face login…"
    if a.hf.get("user"):
        return f"Logged in to Hugging Face as `{a.hf['user']}`."
    return "Not logged in to Hugging Face: names found on this computer are offered. Log in on the Hugging Face page."
