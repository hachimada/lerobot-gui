# Development

## How it is built

```
src/lerobot_gui/
  commands/     the pages: one field per lerobot flag, and the command line they make (Python)
  adapters/     everything that knows lerobot: option listing, arm check, output parsing, the files it
                writes (datasets, training runs, calibration files), logins
  api/          FastAPI routes (/api/form/{page}, /api/jobs, ...)
  schemas.py    the shapes the API answers with (the frontend's types are generated from them)
  jobs.py       runs the commands: process groups, output, stdin, signals, one robot command at a time
  web/          the frontend build (generated, not in git)
frontend/       React + TypeScript (Vite)
tests/          pytest; tests/contract needs lerobot, tests/e2e serves a fake machine for the browser tests
```

The backend owns the commands: the frontend sends the values entered so far to
`POST /api/form/{page}` and renders the fields, messages and command line it gets back.
Run (`POST /api/form/{page}/run`) builds the same command on the server, so what runs is what
was previewed.

## Following lerobot

Defaults, choices, types and required flags are read from the installed lerobot's config classes.
The GUI only knows which flags its fields write (`commands/`) and lerobot's output and file formats
(`adapters/`). The contract tests (`-m lerobot`) check both against the installed lerobot: each
field is still an option, the built commands parse with lerobot's CLI parser with every value in
the config, and lerobot's output (its own code, devices faked), datasets and training runs are
still read. To move to a new lerobot, bump the `lerobot[all]` tag in the `dev` group of
`pyproject.toml`, `uv sync`, and run `uv run pytest -m lerobot`.

## Tests and checks

```bash
uv sync                                  # Python 3.12, lerobot[all] at the pinned tag, dev tools
uv run pytest                            # unit + API + lerobot contract tests
uv run pytest -m "not lerobot"           # without the (slower) contract tests
LEROBOT_GUI_TESTS_WITHOUT_LEROBOT=1 uv run pytest -m "not lerobot"   # ...and check they don't import lerobot
uv run ruff check && uv run ruff format --check && uv run pyright

cd frontend && npm ci
npm test                                 # vitest
npm run lint && npm run check:api && npm run typecheck
npm run e2e                              # build + Playwright against tests/e2e/serve.py
                                         # (PW_CHANNEL=chrome uses the installed Chrome)
```

The API's responses are declared in `src/lerobot_gui/schemas.py`. After changing one (or a route),
`npm run gen:api` in `frontend/` writes the OpenAPI document (`frontend/openapi.json`) and the
TypeScript types generated from it (`frontend/src/api/schema.ts`); `tests/test_openapi.py` and
`npm run check:api` fail while they are out of date.

`uvx pre-commit install` runs ruff, pyright, eslint and tsc on every commit.

CI (`.github/workflows/`): `ci.yml` runs all of the above on pushes and pull requests;
`lerobot-main.yml` runs the contract tests against lerobot's main branch every week.

## Frontend with hot reload

The backend with a fixed token, and Vite proxying `/api` to it:

```bash
LEROBOT_GUI_TOKEN=dev uv run lerobot-gui --no-open --root /path/to/workspace
cd frontend && LEROBOT_GUI_TOKEN=dev npm run dev
```
