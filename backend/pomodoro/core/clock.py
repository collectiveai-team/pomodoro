"""Clock abstraction (ADR-0003): answers only "what time is it now".

The Timer state machine (a later ticket) depends on this Protocol so tests can advance time by
hand instead of sleeping; this module ships the Protocol and the real system implementation so
the app factory has something genuine to wire as a dependency provider.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """A time source. The only question it answers is "what time is it now"."""

    def now(self) -> datetime:
        """Return the current, timezone-aware time."""
        ...


class SystemClock:
    """Real wall-clock Clock, backed by the system time in UTC."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)


def get_clock() -> Clock:
    """Dependency provider for the real system Clock (overridable in tests)."""
    return SystemClock()
