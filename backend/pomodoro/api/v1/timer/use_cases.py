"""Timer lifecycle orchestration; core owns all state-transition rules (T12)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pomodoro.core.tasks import Task, TaskId, TaskNotFoundError, TaskRepository
from pomodoro.core.timer import (
    BREAK_LONG_SECONDS,
    BREAK_SHORT_SECONDS,
    POMODORO_SECONDS,
    InvalidTimerTransitionError,
    Timer,
    TimerPhase,
    TimerRepository,
    active_seconds,
    pause,
    resume,
    settle,
    start,
    stop,
)

if TYPE_CHECKING:
    from datetime import datetime

    from pomodoro.core.clock import Clock
    from pomodoro.core.users import UserId


@dataclass(frozen=True, slots=True)
class TimerSnapshot:
    """The complete settled Timer view returned to HTTP presentation code."""

    timer: Timer
    server_now: datetime
    task: Task | None
    remaining_seconds: int | None


class TimerPhaseConflictError(Exception):
    """A stale Timer action, carrying the current settled view for client resynchronization."""

    def __init__(self, snapshot: TimerSnapshot) -> None:
        super().__init__("Timer phase no longer matches the caller's view.")
        self.snapshot = snapshot


def read_timer(
    *,
    user_id: UserId,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
) -> TimerSnapshot:
    """Settle and return the caller's durable Timer view."""
    now = clock.now()
    timer = _settle_and_persist(user_id=user_id, now=now, timer_repository=timer_repository)
    return _snapshot(user_id=user_id, timer=timer, now=now, task_repository=task_repository)


def start_timer(
    *,
    user_id: UserId,
    task_id: TaskId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
) -> TimerSnapshot:
    """Settle, phase-guard, and start a Pomodoro for one of the caller's Active Tasks."""
    now = clock.now()
    current = _settle_and_persist(user_id=user_id, now=now, timer_repository=timer_repository)
    _ensure_expected_phase(
        current, expected_phase, user_id=user_id, now=now, task_repository=task_repository
    )
    task = task_repository.get_by_id(user_id, task_id)
    if task is None or not task.is_active:
        raise TaskNotFoundError(f"Active Task {task_id} not found.")

    try:
        timer = start(current, task_id=task_id, now=now)
    except InvalidTimerTransitionError as exc:
        raise TimerPhaseConflictError(
            _snapshot(user_id=user_id, timer=current, now=now, task_repository=task_repository)
        ) from exc
    timer_repository.save(user_id, timer)
    return _snapshot(user_id=user_id, timer=timer, now=now, task_repository=task_repository)


def pause_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
) -> TimerSnapshot:
    """Settle, phase-guard, and pause a running Pomodoro."""
    return _transition_timer(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        transition=pause,
    )


def resume_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
) -> TimerSnapshot:
    """Settle, phase-guard, and resume a paused Pomodoro."""
    return _transition_timer(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        transition=resume,
    )


def stop_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
) -> TimerSnapshot:
    """Settle, phase-guard, and move a Pomodoro to AskingToLog."""
    return _transition_timer(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        transition=stop,
    )


def _transition_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    transition: TimerTransition,
) -> TimerSnapshot:
    """Apply a phase-guarded core transition after exactly one lazy settlement."""
    now = clock.now()
    current = _settle_and_persist(user_id=user_id, now=now, timer_repository=timer_repository)
    _ensure_expected_phase(
        current, expected_phase, user_id=user_id, now=now, task_repository=task_repository
    )
    try:
        timer = transition(current, now=now)
    except InvalidTimerTransitionError as exc:
        raise TimerPhaseConflictError(
            _snapshot(user_id=user_id, timer=current, now=now, task_repository=task_repository)
        ) from exc
    timer_repository.save(user_id, timer)
    return _snapshot(user_id=user_id, timer=timer, now=now, task_repository=task_repository)


class TimerTransition(Protocol):
    """The shared signature of the core pause, resume, and stop transitions."""

    def __call__(self, timer: Timer, *, now: datetime) -> Timer:
        """Return the next Timer state for `timer` at `now`."""
        ...


def _settle_and_persist(
    *, user_id: UserId, now: datetime, timer_repository: TimerRepository
) -> Timer:
    """Settle once and atomically store any newly completed Pomodoro with its Timer."""
    persisted_timer = timer_repository.get(user_id) or Timer()
    settlement = settle(persisted_timer, now)
    if settlement.completed_pomodoro is not None:
        timer_repository.save_completed_settlement(
            user_id, settlement.timer, settlement.completed_pomodoro
        )
    elif settlement.timer != persisted_timer:
        timer_repository.save(user_id, settlement.timer)
    return settlement.timer


def _ensure_expected_phase(
    timer: Timer,
    expected_phase: TimerPhase,
    *,
    user_id: UserId,
    now: datetime,
    task_repository: TaskRepository,
) -> None:
    """Raise a resynchronization error when a stale tab names another Timer phase."""
    if timer.phase is not expected_phase:
        raise TimerPhaseConflictError(
            _snapshot(user_id=user_id, timer=timer, now=now, task_repository=task_repository)
        )


def _snapshot(
    *, user_id: UserId, timer: Timer, now: datetime, task_repository: TaskRepository
) -> TimerSnapshot:
    """Build the Timer's HTTP-neutral view, resolving its retained Task only for this User."""
    task = None if timer.task_id is None else task_repository.get_by_id(user_id, timer.task_id)
    return TimerSnapshot(
        timer=timer,
        server_now=now,
        task=task,
        remaining_seconds=_remaining_seconds(timer, now),
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
