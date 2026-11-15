"""The guard that keeps the tests off the network (netguard.py)."""

import socket

import pytest

from . import netguard


def test_beyond_this_computer_is_refused_and_recorded_but_this_computer_is_reachable():
    n = len(netguard.attempts)
    with pytest.raises(OSError):
        socket.create_connection(("example.com", 443), timeout=1)
    with socket.socket() as s, pytest.raises(OSError):
        s.connect(("192.0.2.1", 80))  # an address, no lookup
    assert netguard.attempts[n:] == ["lookup example.com", "192.0.2.1:80"]
    del netguard.attempts[n:]  # refused on purpose here: not a failure of this test
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        socket.create_connection(server.getsockname(), timeout=1).close()
    assert socket.getaddrinfo("localhost", 80)
    assert netguard.attempts[n:] == []
