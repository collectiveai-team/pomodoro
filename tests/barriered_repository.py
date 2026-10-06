"""A repository decorator that forces a concurrent read-modify-write interleaving.

Shared by the Timer-settle/log and duplicate-create/register concurrency
regressions: each reproduces a race whose window is real but narrow, and
`pytest-randomly` plus the house test strategy both require deterministic
tests, so the interleaving is forced here rather than left to thread
scheduling.
"""

from __future__ import annotations

import contextlib
import threading
from typing import Any

BARRIER_TIMEOUT_SECONDS = 10


class BarrieredRepository:
    """Delegates everything to `inner`, holding the first `parties` `read_method` calls.

    Every racer therefore finishes its read before any racer gets to write.
    Only the first `parties` reads are held: a corrected implementation may
    legitimately re-read after losing the race, and must not deadlock against
    a barrier that is already satisfied.
    """

    def __init__(self, inner: object, parties: int, read_method: str) -> None:
        self._inner = inner
        self._parties = parties
        self._read_method = read_method
        self._barrier = threading.Barrier(parties)
        self._lock = threading.Lock()
        self._arrived = 0

    def _hold(self) -> None:
        with self._lock:
            hold = self._arrived < self._parties
            self._arrived += 1
        if hold:
            # Fix-tolerance: never deadlock if a correction changes the read count.
            with contextlib.suppress(threading.BrokenBarrierError):
                self._barrier.wait(timeout=BARRIER_TIMEOUT_SECONDS)

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name != self._read_method:
            return attribute

        def gated(*args: Any, **kwargs: Any) -> Any:
            result = attribute(*args, **kwargs)
            self._hold()
            return result

        return gated
