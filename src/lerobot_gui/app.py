"""The FastAPI application: API routes and the page (the React build in web/)."""

from __future__ import annotations

import html
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import api
from .api.deps import Ctx, Listings, lerobot_listings
from .discovery import Discovery
from .jobs import JobError, JobManager
from .security import check_host
from .settings import Settings

#: `npm run build` in frontend/ writes here
WEB_DIR = Path(__file__).parent / "web"
TOKEN_PLACEHOLDER = "__TOKEN__"

NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>LeRobot GUI</title>
<body style="font:15px system-ui;margin:48px;max-width:640px">
<h1>The frontend isn't built</h1>
<p>Build it once (needs Node.js 22+), then reload:</p>
<pre style="background:#f4f4f5;padding:12px;border-radius:8px">cd frontend
npm ci
npm run build</pre>
<p>It is written to <code>{web}</code>.</p>
</body>"""


class ImmutableStatic(StaticFiles):
    """Vite's hashed asset files: a new build has new names, so they can be cached for good."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def create_app(
    s: Settings, jobs: JobManager | None = None, web_dir: Path = WEB_DIR, listings: Listings | None = None
) -> FastAPI:
    jobs = jobs or JobManager(s)
    discovery = Discovery(s, run_dirs=lambda: list(jobs.train_dirs))
    ctx = Ctx(settings=s, jobs=jobs, discovery=discovery, listings=listings or lerobot_listings())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await ctx.jobs.shutdown()

    app = FastAPI(title="LeRobot GUI", lifespan=lifespan, dependencies=[Depends(check_host)])
    app.state.ctx = ctx

    @app.exception_handler(JobError)
    async def job_error(_request: Request, exc: JobError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)

    if (web_dir / "assets").is_dir():
        app.mount("/assets", ImmutableStatic(directory=web_dir / "assets"), name="assets")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        page = web_dir / "index.html"
        if not page.exists():
            return HTMLResponse(NOT_BUILT.format(web=html.escape(str(web_dir))), status_code=503)
        # the page carries the API token; never cache it (a new build has new asset names)
        text = page.read_text().replace(TOKEN_PLACEHOLDER, s.token)
        return HTMLResponse(text, headers={"Cache-Control": "no-store"})

    app.include_router(api.router)
    return app
