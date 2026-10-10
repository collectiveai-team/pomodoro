"""Adapters that give every Timer transition one timestamp-aware interface."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pomodoro.core.timer import Timer, discard, skip_break

if TYPE_CHECKING:
    from datetime import datetime


class TimerTransition(Protocol):
    """The shared signature of core Timer transitions orchestrated by this package."""

    def __call__(self, timer: Timer, *, now: datetime) -> Timer:
        """Return the next Timer state for `timer` at `now`."""
        ...


def discard_transition(timer: Timer, *, now: datetime) -> Timer:
    """Adapt discard's timestamp-free core interface to the shared transition seam."""
    del now
    return discard(timer)


def skip_break_transition(timer: Timer, *, now: datetime) -> Timer:
    """Adapt skip_break's timestamp-free core interface to the shared transition seam."""
    del now
    return skip_break(timer)
