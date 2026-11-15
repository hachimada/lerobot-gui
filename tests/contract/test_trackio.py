"""The `trackio show` the Trackio page runs, against the installed Trackio (it comes with lerobot's training).

Trackio's own command line reads the GUI's arguments; the dashboard itself isn't started.
"""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("trackio")
pytestmark = pytest.mark.lerobot

from ..commands_helpers import build  # noqa: E402


def test_trackio_reads_the_dashboard_the_page_asks_for(settings, monkeypatch):
    import trackio.cli

    args, m = build(settings, "trackio", {"project": "pick"})
    assert not m.errors
    shown: list[dict] = []
    monkeypatch.setattr(trackio.cli, "show", lambda **kw: shown.append(kw))
    monkeypatch.setattr(sys, "argv", ["trackio", *args])
    trackio.cli.main()
    [kw] = shown
    assert kw["project"] == "pick"
    assert kw["host"] is None  # trackio's own default: this computer only
