"""CES-17 · in-memory brute-force throttling for login/register (User Story 12).

`RateLimiter` is a small, swappable seam (`InMemoryRateLimiter` the only v1 implementation):
callers pass a key (IP + normalized email, see `rate_limit_key`) and the injectable `Clock`'s
`now()` (ADR-0003), never a real sleep, so tests advance a fake clock past the window instead of
sleeping through it. The in-memory, single-process store is an accepted v1 limitation (per the
spec's Out of Scope on real-time infra) and will not coordinate across multiple backend
instances.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Protocol

from pomodoro.core.users import normalize_email

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)


class RateLimitExceededError(Exception):
    """Raised when a key (IP + email) has reached the failed-attempt threshold."""


class RateLimiter(Protocol):
    """Throttles failed login/register attempts, keyed by an opaque string."""

    def check(self, key: str, now: datetime) -> None:
        """Raise `RateLimitExceededError` if `key` is currently over the threshold."""
        ...

    def record_failure(self, key: str, now: datetime) -> None:
        """Record one failed attempt for `key` at `now`."""
        ...


class InMemoryRateLimiter:
    """Sliding-window `RateLimiter` backed by a plain in-memory dict."""

    def __init__(self, *, max_failures: int = MAX_FAILURES, window: timedelta = WINDOW) -> None:
        self._max_failures = max_failures
        self._window = window
        self._failures: dict[str, list[datetime]] = defaultdict(list)

    def check(self, key: str, now: datetime) -> None:
        """Raise `RateLimitExceededError` once `key` has `max_failures` failures in `window`."""
        if len(self._recent_failures(key, now)) >= self._max_failures:
            raise RateLimitExceededError("Too many failed attempts. Try again later.")

    def record_failure(self, key: str, now: datetime) -> None:
        """Append a failure timestamp for `key`, pruning entries outside the window."""
        recent = self._recent_failures(key, now)
        recent.append(now)
        self._failures[key] = recent

    def _recent_failures(self, key: str, now: datetime) -> list[datetime]:
        cutoff = now - self._window
        return [moment for moment in self._failures[key] if moment > cutoff]


def rate_limit_key(client_ip: str, email: str) -> str:
    """Return the IP + normalized-email key a login/register attempt is throttled by."""
    return f"{client_ip}:{normalize_email(email)}"
