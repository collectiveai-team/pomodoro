"""Framework-free current-day Timer summary rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from pomodoro.core.timer import Pomodoro, PomodoroStatus, TimerPhase

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

LONG_BREAK_CADENCE = 5


@dataclass(frozen=True, slots=True)
class DailySummary:
    """Completed-Pomodoro counts displayed with a User's live Timer."""

    pomodoros_completed_today: int
    pomodoros_until_long_break: int


def completed_pomodoro_count(pomodoros: Iterable[Pomodoro]) -> int:
    """Return the all-time count that determines the next Break kind."""
    return sum(pomodoro.status is PomodoroStatus.COMPLETED for pomodoro in pomodoros)


def pomodoros_until_long_break(completed: int, phase: TimerPhase) -> int:
    """Return how many more Pomodoros precede the next long Break.

    Right after a Pomodoro completes (ReadyForNext) the long Break may be due now, so the count
    reaches 0. In every other phase it counts 5..1 toward the long Break.
    """
    if phase is TimerPhase.READY_FOR_NEXT:
        return (-completed) % LONG_BREAK_CADENCE
    return LONG_BREAK_CADENCE - completed % LONG_BREAK_CADENCE


def summarize_day(
    *, pomodoros: Iterable[Pomodoro], now: datetime, time_zone: str, phase: TimerPhase
) -> DailySummary:
    """Summarize completed Pomodoros on `now`'s local day and until a long Break."""
    zone = ZoneInfo(time_zone)
    local_day = now.astimezone(zone).date()
    completed = tuple(
        pomodoro for pomodoro in pomodoros if pomodoro.status is PomodoroStatus.COMPLETED
    )
    completed_today = sum(
        pomodoro.ended_at.astimezone(zone).date() == local_day for pomodoro in completed
    )
    return DailySummary(
        pomodoros_completed_today=completed_today,
        pomodoros_until_long_break=pomodoros_until_long_break(len(completed), phase),
    )
