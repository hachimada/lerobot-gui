"""The API's OpenAPI document: the frontend's types are generated from it (`npm run gen:api` in frontend).

    uv run python -m tests.openapi    writes frontend/openapi.json

tests/test_openapi.py fails when it is out of date.
"""

from __future__ import annotations

import json
from pathlib import Path

from lerobot_gui.app import create_app
from lerobot_gui.settings import Settings

FILE = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"


def text() -> str:
    """The document, as the file holds it (the settings don't show in it)."""
    where = Path("/path/to/workspace")
    s = Settings(
        root=where, hf_home=where / "hf", calibration={}, bin_dir=where / "bin", config_dir=where / "config", env={}
    )
    return json.dumps(create_app(s, web_dir=where / "web").openapi(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    FILE.write_text(text())
