"""Models on the Hugging Face Hub, for picking a pretrained policy."""

from __future__ import annotations

from fastapi import APIRouter

from .. import schemas

router = APIRouter()


@router.get("/hub/models", response_model=schemas.HubModels)
def hub_models(refresh: bool = False) -> dict:
    from ..adapters import accounts, hub

    login = accounts.peek("hf") or {}
    return hub.models(login.get("user") if login.get("logged_in") else None, refresh)
