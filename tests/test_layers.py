"""The adapters (what knows lerobot and the libraries) don't use the modules that use them."""

import ast
from pathlib import Path

import lerobot_gui

ADAPTERS = Path(lerobot_gui.__file__).parent / "adapters"
#: what an adapter may import from the GUI itself: helpers that import nothing of it
ALLOWED = {"cache", "paths", "settings", "schemas"}


def _imported(path: Path) -> set[str]:
    """The GUI's own modules outside adapters/ that `path` imports (also inside functions)."""
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.level == 2:
            out |= {node.module.split(".")[0]} if node.module else {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            parts = (node.module or "").split(".")
            if parts[0] == "lerobot_gui" and len(parts) > 1:
                out.add(parts[1])
    return out - {"adapters"}


def test_adapters_import_only_helpers():
    found = {p.name: _imported(p) - ALLOWED for p in sorted(ADAPTERS.glob("*.py"))}
    assert {name: mods for name, mods in found.items() if mods} == {}
