"""Paths as the GUI shows them: the home dir as `~`.

The commands run without a shell, so nothing would expand a `~` in their arguments: the command
builder expands a leading `~` itself (`expand`), and lerobot always gets the full path.
"""

from __future__ import annotations

from pathlib import Path


def _home() -> str:
    return str(Path.home()).rstrip("/")


def tilde(path: str | Path) -> str:
    """`path` with the home dir written `~` (`/home/alice/x` -> `~/x`)."""
    text, home = str(path), _home()
    if not home:
        return text
    if text == home:
        return "~"
    return "~" + text[len(home) :] if text.startswith(home + "/") else text


def shown(path: Path, root: Path) -> str:
    """`path` as the GUI shows and offers it: relative to the workspace `root` when it is inside it (the
    commands run there), else with `~` for the home dir (the command builder expands it)."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return tilde(path)


def expand(text: str) -> str:
    """A leading `~` (`~` or `~/...`) as the home dir, as a shell would expand it."""
    return _home() + text[1:] if text == "~" or text.startswith("~/") else text
