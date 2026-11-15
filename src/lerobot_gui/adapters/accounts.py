"""Hugging Face login state for the GUI, plus local name candidates.

Logins and logouts go through the public API of huggingface_hub, so secrets are only written where
its tools keep them; they are never returned or logged. The status calls reach huggingface.co with
the stored credentials, so results are cached.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..cache import Cache
from ..paths import tilde

CACHE_S = 600
_cache: Cache[str, dict] = Cache(CACHE_S)


def _short(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}".splitlines()[0][:240]


def peek(key: str) -> dict | None:
    """The last status of "hf", however old, without reaching the network."""
    return _cache.last(key)


# ------------------------------------------------------------------ hugging face


def hf_saved_login() -> str | None:
    """Where `hf auth login` keeps the token, when a token is saved there (the token isn't read)."""
    from huggingface_hub import constants

    path = Path(constants.HF_TOKEN_PATH)
    return tilde(path) if path.is_file() else None


def _http_status(exc: Exception) -> int | None:
    """The HTTP status of a huggingface_hub error (HfHubHTTPError carries the response); None without one."""
    return getattr(getattr(exc, "response", None), "status_code", None)


def _hf_status() -> dict:
    from huggingface_hub import constants, get_token, whoami

    token = get_token()
    source = "HF_TOKEN environment variable" if os.environ.get("HF_TOKEN") else tilde(constants.HF_TOKEN_PATH)
    if not token:
        return {"logged_in": False, "where": source}
    try:
        info = whoami(token=token)
    except Exception as exc:
        if _http_status(exc) == 401:
            return {"logged_in": False, "error": "The saved token is invalid or expired.", "where": source}
        text = _short(exc)
        return {
            "logged_in": True,
            "user": None,
            "orgs": [],
            "error": f"Could not reach Hugging Face: {text}",
            "where": source,
        }
    return {
        "logged_in": True,
        "user": info.get("name"),
        "orgs": [o["name"] for o in info.get("orgs", []) if o.get("name")],
        "token_name": (info.get("auth", {}).get("accessToken", {}) or {}).get("displayName"),
        "token_role": (info.get("auth", {}).get("accessToken", {}) or {}).get("role"),
        "where": source,
    }


def hf_status(refresh: bool = False) -> dict:
    return _cache.get("hf", _hf_status, refresh=refresh)


def hf_login(token: str) -> dict:
    from huggingface_hub import login, whoami

    token = token.strip()
    if not token:
        raise ValueError("Paste a Hugging Face access token.")
    try:
        whoami(token=token)  # validate before saving
    except Exception as exc:
        raise ValueError(f"Hugging Face rejected the token: {_short(exc)}") from exc
    login(token=token, add_to_git_credential=False, skip_if_logged_in=False)
    return hf_status(refresh=True)


def hf_logout() -> dict:
    """As `hf auth logout`: the saved tokens are removed."""
    from huggingface_hub import logout

    if os.environ.get("HF_TOKEN"):
        raise ValueError("The token comes from the HF_TOKEN environment variable: unset it to log out.")
    try:
        logout()
    except OSError as exc:  # still logged in through the environment
        raise ValueError(str(exc).splitlines()[0]) from exc
    return hf_status(refresh=True)
