"""The `Clock` Protocol (ADR-0003): `core` only ever asks "what time is it now".

No ticking, scheduler or background job lives in `core` — the Timer state
machine settles lazily against a single `Clock.now()` call per read/action, and
tests inject a fake `Clock` advanced by hand instead of sleeping real time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class Clock(Protocol):
    """Supplies the current aware datetime; nothing else."""

    def now(self) -> datetime:
        """Return the current aware datetime (UTC)."""
        ...
