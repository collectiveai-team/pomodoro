"""Timer read-model construction and stale-phase resynchronization support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pomodoro.core.daily_summary import DailySummary, summarize_day
from pomodoro.core.timer import (
    BREAK_LONG_SECONDS,
    BREAK_SHORT_SECONDS,
    POMODORO_SECONDS,
    PomodoroRepository,
    Timer,
    TimerPhase,
    active_seconds,
)

if TYPE_CHECKING:
    from datetime import datetime

    from pomodoro.core.tasks import Task, TaskRepository
    from pomodoro.core.users import UserId


@dataclass(frozen=True, slots=True)
class TimerSnapshot:
    """The complete settled Timer view returned to HTTP presentation code."""

    timer: Timer
    server_now: datetime
    task: Task | None
    remaining_seconds: int | None
    daily_summary: DailySummary


class TimerPhaseConflictError(Exception):
    """A stale Timer action, carrying the current settled view for client resynchronization."""

    def __init__(self, snapshot: TimerSnapshot) -> None:
        super().__init__("Timer phase no longer matches the caller's view.")
        self.snapshot = snapshot


def phase_conflict(
    user_id: UserId,
    timer: Timer,
    now: datetime,
    task_repository: TaskRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerPhaseConflictError:
    """Build the settled Timer snapshot used to resynchronize a stale caller."""
    return TimerPhaseConflictError(
        snapshot(
            user_id=user_id,
            timer=timer,
            now=now,
            task_repository=task_repository,
            pomodoro_repository=pomodoro_repository,
            time_zone=time_zone,
        )
    )


def ensure_expected_phase(
    timer: Timer,
    expected_phase: TimerPhase,
    *,
    user_id: UserId,
    now: datetime,
    task_repository: TaskRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> None:
    """Raise a resynchronization error when a stale tab names another Timer phase."""
    if timer.phase is not expected_phase:
        raise TimerPhaseConflictError(
            snapshot(
                user_id=user_id,
                timer=timer,
                now=now,
                task_repository=task_repository,
                pomodoro_repository=pomodoro_repository,
                time_zone=time_zone,
            )
        )


def snapshot(
    *,
    user_id: UserId,
    timer: Timer,
    now: datetime,
    task_repository: TaskRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Build the Timer view, including its caller-local daily summary."""
    task = None if timer.task_id is None else task_repository.get_by_id(user_id, timer.task_id)
    return TimerSnapshot(
        timer=timer,
        server_now=now,
        task=task,
        remaining_seconds=_remaining_seconds(timer, now),
        daily_summary=summarize_day(
            pomodoros=pomodoro_repository.list_for_user(user_id),
            now=now,
            time_zone=time_zone,
        ),
    )


def _remaining_seconds(timer: Timer, now: datetime) -> int | None:
    """Return remaining active time for an active or paused phase, otherwise no countdown."""
    if timer.phase in {TimerPhase.POMODORO_RUNNING, TimerPhase.POMODORO_PAUSED}:
        return POMODORO_SECONDS - active_seconds(timer, now)
    if timer.phase in {TimerPhase.BREAK_RUNNING, TimerPhase.BREAK_PAUSED}:
        duration = (
            BREAK_LONG_SECONDS
            if timer.break_kind is not None and timer.break_kind.value == "long"
            else BREAK_SHORT_SECONDS
        )
        return duration - active_seconds(timer, now)
    return None
