"""Presets: a command page's values saved under a name, to load back later.

A preset is what the page's values are (flag-keyed, plus the GUI's own `gui.*` choices): only what
was entered, so an empty field stays lerobot's default when it is loaded. The Hardware page isn't
part of it. Each is a JSON file, <config dir>/presets/<page>/<name>.json, which can be edited or
copied by hand.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .settings import Settings

MAX_NAME = 80


class PresetError(ValueError):
    pass


def check_name(name: str) -> str:
    name = name.strip()
    if not name or len(name) > MAX_NAME or name.startswith(".") or any(c in name for c in "/\\\0"):
        raise PresetError("A preset name has 1 to 80 characters, without `/` or `\\`, and doesn't start with `.`.")
    return name


def _dir(s: Settings, page: str) -> Path:
    return s.config_dir / "presets" / page


def _clean(values: dict) -> dict:
    """The entered values: no empty ones (they are lerobot's defaults anyway)."""
    return {str(k): v for k, v in values.items() if v is not None and v != "" and v != [] and v != {}}


def _read(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("values"), dict):
        return None
    return data


def listing(s: Settings, page: str) -> list[dict]:
    """[{name, saved, count}], by name."""
    out = []
    for path in _dir(s, page).glob("*.json"):
        data = _read(path)
        if data is not None:
            out.append({"name": path.stem, "saved": data.get("saved"), "count": len(data["values"])})
    return sorted(out, key=lambda p: p["name"].lower())


def load(s: Settings, page: str, name: str) -> dict:
    name = check_name(name)
    data = _read(_dir(s, page) / f"{name}.json")
    if data is None:
        raise PresetError(f"No preset `{name}`.")
    return {"name": name, "saved": data.get("saved"), "values": _clean(data["values"])}


def save(s: Settings, page: str, name: str, values: dict) -> dict:
    name = check_name(name)
    folder = _dir(s, page)
    folder.mkdir(parents=True, exist_ok=True)
    data = {"page": page, "name": name, "saved": time.time(), "values": _clean(values)}
    tmp = folder / f".{name}.json.tmp"
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(folder / f"{name}.json")  # whole or not at all
    return {"name": name, "saved": data["saved"], "values": data["values"]}


def delete(s: Settings, page: str, name: str) -> None:
    path = _dir(s, page) / f"{check_name(name)}.json"
    if not path.is_file():
        raise PresetError(f"No preset `{name}`.")
    path.unlink()
