"""The command pages: their fields for the current values, the command they build, and Run."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import commands, schemas
from ..adapters import accounts
from ..commands.context import Accounts, Context
from ..commands.extras import visible_options
from ..commands.model import Page
from .deps import CtxDep

router = APIRouter()


class FormRequest(BaseModel):
    #: page id -> the values the user changed (the rest are defaults)
    values: dict[str, dict] = {}
    #: the arm check that stopped the last Run of this page
    preflight: schemas.ArmCheck | None = None


class RunRequest(BaseModel):
    values: dict[str, dict] = {}
    force: bool = False  # skip the swapped-arms check


def _accounts() -> Accounts:
    hf = accounts.peek("hf")
    return Accounts(loaded=hf is not None, hf=hf or {})


def _context(ctx: CtxDep, page_id: str, values: dict[str, dict]) -> tuple[Page, Context]:
    """A command page (the others, Hardware's included, have routes of their own) and its context."""
    try:
        page = commands.get_page(page_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    if page.exe is None:
        raise HTTPException(404, f"{page.title} runs no command")
    s = ctx.settings
    c = commands.make_context(
        ctx.discovery.snapshot(), _accounts(), values, root=s.root, hf_home=s.hf_home, page=page.id
    )
    return page, c


@router.get("/pages", response_model=schemas.Pages)
def pages() -> schemas.Pages:
    return {"pages": commands.page_list(), "nav": list(commands.NAV)}


@router.post("/form/{page_id}", response_model=schemas.FormResponse)
def form(ctx: CtxDep, page_id: str, req: FormRequest) -> schemas.FormResponse:
    """Fields, command line and messages for the values so far (fast: never imports lerobot)."""
    page, c = _context(ctx, page_id, req.values)
    return commands.form(page, c, ctx.listings.cached, preflight=req.preflight)


@router.post("/form/{page_id}/options", response_model=schemas.OptionsListing)
def form_options(ctx: CtxDep, page_id: str, req: FormRequest) -> dict:
    """The "All options" listing for the current values (the first call imports lerobot: seconds)."""
    page, c = _context(ctx, page_id, req.values)
    query = commands.extras.options_query(page, c)
    if query is None:
        raise HTTPException(404, f"{page.title} has no option listing")
    try:
        listing = ctx.listings.full(*query)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    assert listing is not None
    return {"options": visible_options(page, c, listing), "errors": listing["errors"]}


@router.post("/form/{page_id}/run", response_model=schemas.JobInfo)
def run(ctx: CtxDep, page_id: str, req: RunRequest) -> schemas.JobInfo:
    """Build the command from the values (exactly as previewed) and start it."""
    page, c = _context(ctx, page_id, req.values)
    args, m = commands.build(page, c, ctx.listings.full)
    if m.errors:
        detail = {"message": "Fix the errors first: " + " ".join(m.texts("err")), "messages": m.to_json()}
        raise HTTPException(400, detail)
    assert page.exe is not None  # a command page (_context)
    return ctx.jobs.start(page.exe, args, force=req.force, page=page.id).info()
