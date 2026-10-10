"""Timer lifecycle orchestration; core owns all state-transition rules (T12-T13)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pomodoro.api.v1.timer.snapshots import (
    TimerPhaseConflictError,
    TimerSnapshot,
    ensure_expected_phase,
    phase_conflict,
    snapshot,
)
from pomodoro.api.v1.timer.transitions import (
    TimerTransition,
    discard_transition,
    skip_break_transition,
)
from pomodoro.core.daily_summary import completed_pomodoro_count
from pomodoro.core.tasks import TaskId, TaskNotFoundError, TaskRepository
from pomodoro.core.timer import (
    InvalidTimerTransitionError,
    PomodoroRepository,
    Timer,
    TimerPhase,
    TimerRepository,
    log,
    next_pomodoro,
    pause,
    resume,
    settle,
    start,
    start_break,
    stop,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from pomodoro.core.clock import Clock
    from pomodoro.core.users import UserId

__all__ = [
    "TimerPhaseConflictError",
    "TimerSnapshot",
    "discard_timer",
    "log_timer",
    "next_pomodoro_timer",
    "pause_timer",
    "read_timer",
    "resume_timer",
    "skip_break_timer",
    "start_break_timer",
    "start_timer",
    "stop_timer",
]


def read_timer(
    *,
    user_id: UserId,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle and return the caller's durable Timer view."""
    now = clock.now()
    timer = _settle_and_persist(user_id=user_id, now=now, timer_repository=timer_repository)
    return snapshot(
        user_id=user_id,
        timer=timer,
        now=now,
        task_repository=task_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
    )


def start_timer(
    *,
    user_id: UserId,
    task_id: TaskId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle, phase-guard, and start a Pomodoro for one of the caller's Active Tasks."""
    now, current = _settle_and_guard(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
    )
    task = task_repository.get_by_id(user_id, task_id)
    if task is None or not task.is_active:
        raise TaskNotFoundError(f"Active Task {task_id} not found.")
    return _apply_transition(
        user_id=user_id,
        current=current,
        now=now,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
        apply=lambda: start(current, task_id=task_id, now=now),
    )


def pause_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle, phase-guard, and pause a running Pomodoro or Break."""
    return _transition_timer(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
        transition=pause,
    )


def resume_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle, phase-guard, and resume a paused Pomodoro."""
    return _transition_timer(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
        transition=resume,
    )


def stop_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle, phase-guard, and move a Pomodoro to AskingToLog."""
    return _transition_timer(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
        transition=stop,
    )


def log_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle, phase-guard, and atomically persist an interrupted Pomodoro and Idle Timer."""
    now, current = _settle_and_guard(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
    )
    try:
        logged = log(current, now=now)
    except InvalidTimerTransitionError as exc:
        raise phase_conflict(
            user_id, current, now, task_repository, pomodoro_repository, time_zone
        ) from exc
    timer_repository.save_logged_interruption(user_id, logged.timer, logged.pomodoro)
    return snapshot(
        user_id=user_id,
        timer=logged.timer,
        now=now,
        task_repository=task_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
    )


def discard_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle, phase-guard, and discard an interrupted Pomodoro without recording it."""
    return _transition_timer(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
        transition=discard_transition,
    )


def start_break_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle, phase-guard, and start the Break due after completed Pomodoros."""
    now, current = _settle_and_guard(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
    )
    return _apply_transition(
        user_id=user_id,
        current=current,
        now=now,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
        apply=lambda: start_break(
            current,
            now=now,
            completed_pomodoro_count=completed_pomodoro_count(
                pomodoro_repository.list_for_user(user_id)
            ),
        ),
    )


def skip_break_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle, phase-guard, and skip a running or paused Break."""
    return _transition_timer(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
        transition=skip_break_transition,
    )


def next_pomodoro_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> TimerSnapshot:
    """Settle, phase-guard, and restart a Pomodoro for the completed Task."""
    return _transition_timer(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
        transition=next_pomodoro,
    )


def _transition_timer(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
    transition: TimerTransition,
) -> TimerSnapshot:
    """Apply a phase-guarded core transition after exactly one lazy settlement."""
    now, current = _settle_and_guard(
        user_id=user_id,
        expected_phase=expected_phase,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
    )
    return _apply_transition(
        user_id=user_id,
        current=current,
        now=now,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
        apply=lambda: transition(current, now=now),
    )


def _settle_and_guard(
    *,
    user_id: UserId,
    expected_phase: TimerPhase,
    clock: Clock,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
) -> tuple[datetime, Timer]:
    """Settle once and enforce the caller's expected phase before any transition."""
    now = clock.now()
    current = _settle_and_persist(user_id=user_id, now=now, timer_repository=timer_repository)
    ensure_expected_phase(
        current,
        expected_phase,
        user_id=user_id,
        now=now,
        task_repository=task_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
    )
    return now, current


def _apply_transition(
    *,
    user_id: UserId,
    current: Timer,
    now: datetime,
    task_repository: TaskRepository,
    timer_repository: TimerRepository,
    pomodoro_repository: PomodoroRepository,
    time_zone: str,
    apply: Callable[[], Timer],
) -> TimerSnapshot:
    """Run one core transition, raising a typed conflict, then persist and snapshot it."""
    try:
        timer = apply()
    except InvalidTimerTransitionError as exc:
        raise phase_conflict(
            user_id, current, now, task_repository, pomodoro_repository, time_zone
        ) from exc
    timer_repository.save(user_id, timer)
    return snapshot(
        user_id=user_id,
        timer=timer,
        now=now,
        task_repository=task_repository,
        pomodoro_repository=pomodoro_repository,
        time_zone=time_zone,
    )


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
