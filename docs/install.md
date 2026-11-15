# Install

## 1. Build the frontend

```bash
git clone https://github.com/hachimada/lerobot-gui.git
cd lerobot-gui/frontend
npm ci
npm run build          # writes ../src/lerobot_gui/web/
```

## 2. Install it

The GUI runs the `lerobot-*` commands of the environment it is installed in. There are three ways:

| | When | How |
|---|---|---|
| **A** | lerobot isn't installed yet | lerobot-gui's own environment, which installs lerobot too |
| **B** | lerobot is a dependency of a uv project | `uv add` lerobot-gui to that project |
| **C** | lerobot is in another virtualenv or conda environment | `pip install` lerobot-gui into it |

B and C only require `lerobot>=0.7` and keep the lerobot you have.

**A.** Installs Python 3.12 and `lerobot[all]` v0.7.0 (with torch, several GB). Run it as
`/path/to/lerobot-gui/.venv/bin/lerobot-gui`, or `uv run lerobot-gui` in that directory.

```bash
cd /path/to/lerobot-gui && uv sync
```

**B.**

```bash
cd /path/to/your-project && uv add --editable /path/to/lerobot-gui
```

**C.** Not for a uv project: its next `uv sync` removes packages installed this way.

```bash
pip install -e /path/to/lerobot-gui    # in the activated environment
```

The install is editable: a rebuilt frontend is served on the next page load.

## 3. Serial port permission

The arms are `/dev/ttyACM*` devices of the `dialout` group: `sudo usermod -aG dialout $USER`, then
log in again.

## 4. Start it

```bash
cd /path/to/workspace      # the commands run here
lerobot-gui
```

Ctrl+C stops it; commands still running get Ctrl+C too (lerobot moves the arm back to its start
pose) and are killed after 8 s. Options, environment variables and where files go:
[configuration.md](configuration.md).

## Update

```bash
git pull && (cd frontend && npm ci && npm run build)
```

When `pyproject.toml` changed, update the environment too: `uv sync` (A, B) or
`pip install -e /path/to/lerobot-gui` (C).
