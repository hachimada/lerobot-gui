"""HTTP API (/api/...). Every route needs the page's token (see security.py)."""

from fastapi import APIRouter, Depends

from ..security import check_token
from . import accounts, devices, environment, forms, hardware, hub, jobs, presets, services

router = APIRouter(prefix="/api", dependencies=[Depends(check_token)])
for module in (accounts, devices, environment, forms, hardware, hub, jobs, presets, services):
    router.include_router(module.router)
