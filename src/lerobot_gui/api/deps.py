from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from ..commands.extras import Listing
from ..discovery import Discovery
from ..jobs import JobManager
from ..settings import Settings


@dataclass(frozen=True)
class Listings:
    """lerobot's option listings for a query (command, selections, policy path)."""

    #: the one built already, else None: it never builds one (that imports lerobot's commands)
    cached: Listing
    #: built when there is none yet (the first one imports lerobot: seconds)
    full: Listing


def lerobot_listings() -> Listings:
    """The installed lerobot's listings (adapters/options.py)."""
    from ..adapters import options

    return Listings(cached=options.cached_options, full=options.list_options)


@dataclass
class Ctx:
    settings: Settings
    jobs: JobManager
    discovery: Discovery
    listings: Listings


def get_ctx(request: Request) -> Ctx:
    return request.app.state.ctx


CtxDep = Annotated[Ctx, Depends(get_ctx)]
