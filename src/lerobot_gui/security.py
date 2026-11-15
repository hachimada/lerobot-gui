"""Requests must come from this machine's page: the Host header is checked (blocks other sites and
DNS rebinding) and every /api call carries the per-launch token embedded in the page."""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request


def check_host(request: Request) -> None:
    if request.headers.get("host") not in request.app.state.ctx.settings.allowed_hosts:
        raise HTTPException(403, "Forbidden host")


def check_token(request: Request) -> None:
    given = request.headers.get("x-token") or request.query_params.get("token") or ""
    if not secrets.compare_digest(given, request.app.state.ctx.settings.token):
        raise HTTPException(403, "Invalid token")
