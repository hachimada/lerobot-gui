"""Hugging Face login state, login and logout."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import schemas
from .deps import CtxDep

router = APIRouter()


class SecretRequest(BaseModel):
    secret: str = ""


@router.get("/accounts", response_model=schemas.Accounts)
def accounts_status(ctx: CtxDep, refresh: bool = False) -> dict:
    from ..adapters import accounts

    return {"hf": accounts.hf_status(refresh)}


@router.post("/accounts/hf/login", response_model=schemas.AccountStatus)
def hf_login(req: SecretRequest) -> dict:
    """Log in with a Hugging Face access token (checked first), as `hf auth login` does."""
    from ..adapters import accounts

    try:
        return accounts.hf_login(req.secret)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/accounts/hf/logout", response_model=schemas.AccountStatus)
def hf_logout() -> dict:
    """Remove the saved Hugging Face tokens, as `hf auth logout` does."""
    from ..adapters import accounts

    try:
        return accounts.hf_logout()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
