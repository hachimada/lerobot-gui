# Configuration

## Start options

| Option | |
|---|---|
| `--root DIR` | workspace the commands run in (default: the current directory) |
| `--port N` | port (default 7878) |
| `--no-open` | don't open a browser tab |

## Environment variables

| Variable | |
|---|---|
| `HF_LEROBOT_HOME` | lerobot's data dir: datasets and calibration files (unset: `$HF_HOME/lerobot`). The commands inherit it. |
| `HF_LEROBOT_CALIBRATION` | lerobot's calibration dir (unset: `$HF_LEROBOT_HOME/calibration`) |
| `LEROBOT_GUI_ROOT` | same as `--root` |
| `LEROBOT_GUI_TOKEN` | a fixed API token instead of a random one per launch (for `npm run dev`) |

## Where things go

- Commands run in the workspace: lerobot-train writes its runs to `outputs/train/` unless
  `--output_dir` says otherwise, Find cameras its frames to `outputs/captured_images/`.
- Training runs are listed from the workspace (folders with
  `checkpoints/<step>/pretrained_model/config.json`, up to 5 levels deep, not in hidden folders or
  Python environments) and from the runs the GUI started elsewhere.
- Datasets: `$HF_LEROBOT_HOME/<user>/<name>/`. Calibration files:
  `$HF_LEROBOT_CALIBRATION/<robots|teleoperators>/<class>/<id>.json`.
- A value entered as `~/…` is passed as the full path: the commands run without a shell.
- Presets: `~/.config/lerobot-gui/presets/<page>/<name>.json` (or under `$XDG_CONFIG_HOME`), a
  page's values without the Hardware page.
- The values entered are kept in the browser's local storage of `127.0.0.1:<port>`.
