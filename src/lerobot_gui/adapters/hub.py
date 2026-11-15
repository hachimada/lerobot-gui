"""Policies on the Hugging Face Hub, offered when picking a pretrained policy.

Listing needs the network, so it is cached for an hour and asked for only when the Hub list is
opened. The `lerobot` organization is listed without credentials; the logged-in user's own models
(trained runs pushed with Push to Hub, private ones included) with the saved token.
"""

from __future__ import annotations

from collections.abc import Callable

from ..cache import Cache

ORG = "lerobot"
CACHE_S = 3600
LIMIT = 1000

#: author -> their models
_cache: Cache[str, list[dict]] = Cache(CACHE_S)

#: (author, token: False = anonymous, None = the saved one) -> models
Fetch = Callable[[str, bool | None], list[dict]]


def fetch_models(author: str, token: bool | None) -> list[dict]:
    from huggingface_hub import HfApi

    return [
        {
            "id": m.id,
            "downloads": m.downloads or 0,
            "likes": m.likes or 0,
            "created": m.created_at.date().isoformat() if m.created_at else None,
            "private": bool(m.private),
        }
        for m in HfApi().list_models(author=author, sort="downloads", limit=LIMIT, token=token)
    ]


def models(user: str | None, refresh: bool = False, fetch: Fetch | None = None) -> dict:
    """{"groups": [{"title", "author", "models": [...]}], "error": text or None}, most downloaded first."""
    fetch = fetch or fetch_models
    sources: list[tuple[str, str, bool | None]] = [(ORG, ORG, False)]
    if user and user != ORG:
        sources.append((user, f"{user} (you)", None))
    groups, errors = [], []
    for author, title, token in sources:
        try:
            found = _cache.get(author, lambda a=author, t=token: fetch(a, t), refresh=refresh)
        except Exception as exc:
            errors.append(f"Could not list {author}'s models on the Hub: {f'{type(exc).__name__}: {exc}'[:200]}")
            found = _cache.last(author) or []  # what was listed before, if anything
        groups.append({"title": title, "author": author, "models": found})
    return {"groups": groups, "error": " ".join(errors) or None}


# ------------------------------------------------- the account's own repos

CLOUD_CACHE_S = 600
#: the fields asked for; the Hub refuses the whole request for one it doesn't take (it no longer
#: takes `usedStorage` in listings, though huggingface_hub's types still name it)
_EXPAND = ["private", "downloads", "likes", "lastModified", "createdAt"]
_cloud_cache: Cache[str, dict] = Cache(CLOUD_CACHE_S)

#: owner -> {"datasets": [...], "models": [...]}, with the saved token (private repos included)
FetchRepos = Callable[[str], dict]


def _repo(r, kind: str) -> dict:
    when = getattr(r, "last_modified", None) or getattr(r, "created_at", None)
    return {
        "id": r.id,
        "private": bool(getattr(r, "private", False)),
        "downloads": getattr(r, "downloads", None) or 0,
        "likes": getattr(r, "likes", None) or 0,
        "updated": when.isoformat() if when else None,
        "url": f"https://huggingface.co/{'datasets/' if kind == 'dataset' else ''}{r.id}",
    }


def fetch_repos(owner: str) -> dict:
    from huggingface_hub import HfApi

    api = HfApi()
    return {
        "datasets": [_repo(d, "dataset") for d in api.list_datasets(author=owner, expand=_EXPAND, limit=LIMIT)],  # type: ignore[arg-type]
        "models": [_repo(m, "model") for m in api.list_models(author=owner, expand=_EXPAND, limit=LIMIT)],  # type: ignore[arg-type]
    }


def cloud(user: str | None, orgs: list[str], refresh: bool = False, fetch: FetchRepos | None = None) -> dict:
    """{"owners": [{"owner", "kind" (user/org), "datasets", "models", "error"}]}: the logged-in account's
    datasets and models on the Hub, then each of its organizations', newest first."""
    fetch = fetch or fetch_repos
    owners = [(user, "user")] if user else []
    owners += [(o, "org") for o in orgs if o and o != user]
    out = []
    for owner, kind in owners:
        assert owner is not None
        error = None
        try:
            found = _cloud_cache.get(owner, lambda o=owner: fetch(o), refresh=refresh)
        except Exception as exc:
            # the Hub's own words (they say which part of the request it refused)
            detail = " ".join(str(getattr(exc, "server_message", None) or exc).split())
            error = f"Could not list {owner}'s repos on the Hub: {type(exc).__name__}: {detail[:600]}"
            found = _cloud_cache.last(owner) or {"datasets": [], "models": []}
        newest = {
            k: sorted(found.get(k, []), key=lambda r: r.get("updated") or "", reverse=True)
            for k in ("datasets", "models")
        }
        out.append({"owner": owner, "kind": kind, **newest, "error": error})
    return {"owners": out}
