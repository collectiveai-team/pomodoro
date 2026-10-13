"""Clock abstraction (ADR-0003): answers only "what time is it now"."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class Clock(Protocol):
    """A time source. The only question it answers is "what time is it now"."""

    def now(self) -> datetime:
        """Return the current, timezone-aware time."""
        ...
