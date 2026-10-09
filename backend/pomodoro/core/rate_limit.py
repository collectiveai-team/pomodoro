"""In-memory IP+email failed-login rate limiting (core, T8).

Framework-free: `RateLimiter` tracks failed login/register attempts per
`(ip, email_key)` pair and reports a pair as blocked once `MAX_FAILED_ATTEMPTS`
lands inside `WINDOW` (issue #12 spec story 12). Every call sweeps every
tracked key's attempts against `now` and drops any key left with none, so the
in-memory store never grows unbounded (regression guard for a prior
memory-leak finding) — no background job is needed, consistent with `core`
never scheduling anything (ADR-0003).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

MAX_FAILED_ATTEMPTS = 5
WINDOW = timedelta(minutes=15)


@dataclass
class RateLimiter:
    """Tracks failed login/register attempts per `(ip, email_key)`, in memory."""

    _attempts: dict[tuple[str, str], list[datetime]] = field(default_factory=dict)

    def record_failure(self, *, ip: str, email_key: str, now: datetime) -> None:
        """Record one failed attempt for `(ip, email_key)` at `now`."""
        self._evict_expired(now)
        self._attempts.setdefault((ip, email_key), []).append(now)

    def is_blocked(self, *, ip: str, email_key: str, now: datetime) -> bool:
        """Return whether `(ip, email_key)` has hit `MAX_FAILED_ATTEMPTS` within `WINDOW`."""
        self._evict_expired(now)
        return len(self._attempts.get((ip, email_key), [])) >= MAX_FAILED_ATTEMPTS

    def reset(self, *, ip: str, email_key: str) -> None:
        """Clear `(ip, email_key)`'s recorded failures (e.g. after a successful login)."""
        self._attempts.pop((ip, email_key), None)

    def _evict_expired(self, now: datetime) -> None:
        for key in list(self._attempts):
            fresh = [attempt for attempt in self._attempts[key] if now - attempt < WINDOW]
            if fresh:
                self._attempts[key] = fresh
            else:
                del self._attempts[key]
