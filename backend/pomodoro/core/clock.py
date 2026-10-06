"""The `Clock` seam: core and api depend on this Protocol, never on a wall-clock."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class Clock(Protocol):
    """Answers "what time is it now". No ticking or background scheduling."""

    def now(self) -> datetime: ...
