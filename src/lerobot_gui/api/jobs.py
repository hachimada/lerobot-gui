"""The jobs: their output, input and signals. A job is started only by Run (`/api/form/{page}/run`),
which builds the command on the server."""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import schemas
from .deps import CtxDep

router = APIRouter()


class InputRequest(BaseModel):
    text: str = ""


class SignalRequest(BaseModel):
    name: str = "INT"


@router.get("/jobs", response_model=list[schemas.JobInfo])
def list_jobs(ctx: CtxDep) -> list[schemas.JobInfo]:
    return [j.info() for j in ctx.jobs.list()]


@router.post("/jobs/{job_id}/input", response_model=schemas.Ok)
def job_input(ctx: CtxDep, job_id: str, req: InputRequest) -> dict:
    ctx.jobs.get(job_id).send_input(req.text)
    return {"ok": True}


@router.post("/jobs/{job_id}/signal", response_model=schemas.JobInfo)
def job_signal(ctx: CtxDep, job_id: str, req: SignalRequest) -> schemas.JobInfo:
    job = ctx.jobs.get(job_id)
    job.send_signal(req.name)
    return job.info()


@router.get("/jobs/{job_id}/stream")
async def job_stream(ctx: CtxDep, job_id: str, request: Request, offset: int = 0) -> StreamingResponse:
    """Server-sent events: `info` first (and again when a prompt shows up), `data` chunks of output, then `end`."""
    job = ctx.jobs.get(job_id)

    async def events():
        pos = offset
        ended_at = None
        state = job.state()
        yield f"event: info\ndata: {json.dumps(job.info())}\n\n"
        while True:
            if await request.is_disconnected():
                return
            text, end, reset = job.read(pos)
            if text or reset:
                yield f"data: {json.dumps({'text': text, 'offset': end, 'reset': reset})}\n\n"
                pos = end
                # a prompt appeared or went away: send the info again
                if (now := job.state()) != state:
                    state = now
                    yield f"event: info\ndata: {json.dumps(job.info())}\n\n"
            if not job.running:
                # give the reader thread a moment to drain the pipe
                ended_at = ended_at or time.monotonic()
                if time.monotonic() - ended_at > 0.6 and pos >= job.end_offset:
                    yield f"event: end\ndata: {json.dumps(job.info())}\n\n"
                    return
            await asyncio.sleep(0.1)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})
