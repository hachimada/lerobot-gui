"""Values kept for a while: the Hub's listings, the login state, lerobot's option listings, the workspace scan.

One value per key, built by the caller's function on a miss. A caller that comes while the value is being
built waits for that build instead of building it again. A failed build keeps nothing (the error goes to
every caller waiting for it), and the value before it can still be read (`last`).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Hashable
from concurrent.futures import Future

#: how long a value is kept: seconds, None for as long as the process runs, or a function of the value
type Ttl[V] = float | Callable[[V], float | None] | None


class Cache[K: Hashable, V]:
    def __init__(self, ttl: Ttl[V], clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl
        self._clock = clock
        #: key -> (the value, when it is due to be built again or None)
        self._kept: dict[K, tuple[V, float | None]] = {}
        self._building: dict[K, Future[V]] = {}
        self._lock = threading.Lock()

    def get(self, key: K, build: Callable[[], V], *, refresh: bool = False) -> V:
        """The value under `key`, built when there is none fresh (or `refresh`)."""
        with self._lock:
            pending = self._building.get(key)
            if pending is None:
                hit = None if refresh else self._fresh(key)
                if hit is not None:
                    return hit[0]
                pending = self._building[key] = Future()
                mine = True
            else:
                mine = False
        if not mine:
            return pending.result()
        try:
            value = build()
        except BaseException as exc:
            with self._lock:
                del self._building[key]
            pending.set_exception(exc)
            raise
        ttl = self._ttl(value) if callable(self._ttl) else self._ttl
        with self._lock:
            self._kept[key] = (value, None if ttl is None else self._clock() + ttl)
            del self._building[key]
        pending.set_result(value)
        return value

    def fresh(self, key: K) -> V | None:
        """The value under `key` if it is still fresh, without building it."""
        with self._lock:
            hit = self._fresh(key)
        return hit[0] if hit is not None else None

    def last(self, key: K) -> V | None:
        """The last value built under `key`, however old (None: never built)."""
        with self._lock:
            hit = self._kept.get(key)
        return hit[0] if hit is not None else None

    def clear(self) -> None:
        with self._lock:
            self._kept.clear()

    def _fresh(self, key: K) -> tuple[V, float | None] | None:
        hit = self._kept.get(key)
        if hit is not None and hit[1] is not None and self._clock() >= hit[1]:
            return None
        return hit
