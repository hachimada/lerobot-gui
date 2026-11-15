"""Tests don't reach the network: a name lookup or a connection beyond this computer is refused and
recorded, so a test that reaches for it fails even when the code under test swallows the refusal.

pytest checks after each test (tests/conftest.py); the browser tests' server writes what it refused
to a log the run checks at its end (tests/e2e/serve.py, frontend/e2e/no-network.ts).
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

#: what was refused, in order: "lookup <host>" or "<address>:<port>"
attempts: list[str] = []
_log: Path | None = None
_installed = False


def _local(host: object) -> bool:
    if isinstance(host, bytes):
        host = host.decode(errors="replace")
    h = str(host or "")
    return h in ("", "localhost", "::1") or h.startswith(("127.", "::ffff:127."))


def _refuse(what: str) -> None:
    attempts.append(what)
    print(f"tests don't reach the network: refused {what}", file=sys.stderr, flush=True)
    if _log is not None:
        with _log.open("a") as f:
            f.write(what + "\n")


def install(log: Path | None = None) -> None:
    """Guard this process: lookups and connections beyond this computer fail and are recorded (and
    written to `log`, emptied here, when given)."""
    global _log, _installed
    _log = log
    if log is not None:
        log.write_text("")
    if _installed:
        return
    _installed = True
    lookup = socket.getaddrinfo

    def getaddrinfo(host, *args, **kwargs):
        if not _local(host):
            _refuse(f"lookup {host}")
            raise socket.gaierror(socket.EAI_NONAME, f"tests don't reach the network ({host})")
        return lookup(host, *args, **kwargs)

    def guarded(real):
        def method(self: socket.socket, address):
            inet = self.family in (socket.AF_INET, socket.AF_INET6)
            if inet and isinstance(address, tuple) and not _local(address[0]):
                _refuse(f"{address[0]}:{address[1]}")
                raise ConnectionRefusedError(f"tests don't reach the network ({address[0]})")
            return real(self, address)

        return method

    socket.getaddrinfo = getaddrinfo
    socket.socket.connect = guarded(socket.socket.connect)
    socket.socket.connect_ex = guarded(socket.socket.connect_ex)
