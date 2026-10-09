"""Timer state machine (core, T6): lazy settlement, transitions, Break cadence.

Each User's single Timer row is resolved lazily against a `Clock` (ADR-0003): no
ticking, scheduler or background job lives here. `settle(timer, now)` collapses
a phase that already expired to the *exact instant* it expired, never to
`now`, mirroring `Timer.phase_ended_at`'s own contract (see `entities.py`).
Every transition is otherwise a pure function over a `Timer` snapshot, in the
same style as `core.tasks`/`core.tags`. Persisting a finished Pomodoro is the
caller's job (T13, `database/`): `settle`/`log` only hand back an optional
`PomodoroDraft` describing the row to write, never writing one themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from typing import TYPE_CHECKING

from pomodoro.core.entities import BreakKind, PomodoroStatus, Timer, TimerPhase
from pomodoro.core.errors import TimerActionNotAllowedError

if TYPE_CHECKING:
    from datetime import datetime

    from pomodoro.core.entities import TaskId

POMODORO_SECONDS = 1500
BREAK_SHORT_SECONDS = 300
BREAK_LONG_SECONDS = 600
LONG_BREAK_EVERY = 5

_RUNNING_TO_PAUSED = {
    TimerPhase.POMODORO_RUNNING: TimerPhase.POMODORO_PAUSED,
    TimerPhase.BREAK_RUNNING: TimerPhase.BREAK_PAUSED,
}
_PAUSED_TO_RUNNING = {paused: running for running, paused in _RUNNING_TO_PAUSED.items()}


@dataclass(frozen=True, slots=True)
class PomodoroDraft:
    """A finished Pomodoro run core has computed; the caller persists it (T13)."""

    task_id: TaskId
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    status: PomodoroStatus


@dataclass(frozen=True, slots=True)
class TimerUpdate:
    """The resulting Timer from `settle`/`log`, plus a Pomodoro if one was produced."""

    timer: Timer
    pomodoro: PomodoroDraft | None = None


def derive_break_kind(total_completed_pomodoros: int) -> BreakKind:
    """Long Break every 5th completed Pomodoro — derived from data, never a stored counter."""
    if total_completed_pomodoros % LONG_BREAK_EVERY == 0:
        return BreakKind.LONG
    return BreakKind.SHORT


def _ensure_phase(timer: Timer, *allowed: TimerPhase, action: str) -> None:
    if timer.phase not in allowed:
        raise TimerActionNotAllowedError(action, timer)


def _elapsed_active_seconds(timer: Timer, now: datetime) -> int:
    if timer.running_since is None:
        return 0
    return round((now - timer.running_since).total_seconds())


def _freeze_accumulated(timer: Timer, now: datetime) -> int:
    return timer.accumulated_active_seconds + _elapsed_active_seconds(timer, now)


def settle(timer: Timer, now: datetime) -> TimerUpdate:
    """Lazily resolve an expired phase to the exact instant it expired — never `now`."""
    if timer.phase is TimerPhase.POMODORO_RUNNING and timer.running_since is not None:
        deadline = timer.running_since + timedelta(
            seconds=POMODORO_SECONDS - timer.accumulated_active_seconds
        )
        if now >= deadline:
            return _settle_completed_pomodoro(timer, deadline)
    elif timer.phase is TimerPhase.BREAK_RUNNING and timer.running_since is not None:
        total_seconds = (
            BREAK_LONG_SECONDS if timer.break_kind is BreakKind.LONG else BREAK_SHORT_SECONDS
        )
        deadline = timer.running_since + timedelta(
            seconds=total_seconds - timer.accumulated_active_seconds
        )
        if now >= deadline:
            return TimerUpdate(timer=Timer(user_id=timer.user_id, phase=TimerPhase.IDLE))
    return TimerUpdate(timer=timer)


def _settle_completed_pomodoro(timer: Timer, deadline: datetime) -> TimerUpdate:
    settled = replace(
        timer,
        phase=TimerPhase.READY_FOR_NEXT,
        accumulated_active_seconds=POMODORO_SECONDS,
        running_since=None,
        phase_ended_at=deadline,
    )
    draft = PomodoroDraft(
        task_id=timer.task_id,  # type: ignore[arg-type]  # invariant: set by start()
        started_at=timer.phase_started_at,  # type: ignore[arg-type]  # invariant: set by start()
        ended_at=deadline,
        duration_seconds=POMODORO_SECONDS,
        status=PomodoroStatus.COMPLETED,
    )
    return TimerUpdate(timer=settled, pomodoro=draft)


def start(timer: Timer, *, task_id: TaskId, now: datetime) -> Timer:
    """Idle -> PomodoroRunning, dedicating a fresh Pomodoro to one of the User's Active Tasks."""
    _ensure_phase(timer, TimerPhase.IDLE, action="start")
    return replace(
        timer,
        phase=TimerPhase.POMODORO_RUNNING,
        task_id=task_id,
        break_kind=None,
        phase_started_at=now,
        accumulated_active_seconds=0,
        running_since=now,
        phase_ended_at=None,
    )


def pause(timer: Timer, *, now: datetime) -> Timer:
    """PomodoroRunning -> PomodoroPaused, or BreakRunning -> BreakPaused; freezes active time."""
    _ensure_phase(timer, *_RUNNING_TO_PAUSED, action="pause")
    return replace(
        timer,
        phase=_RUNNING_TO_PAUSED[timer.phase],
        accumulated_active_seconds=_freeze_accumulated(timer, now),
        running_since=None,
    )


def resume(timer: Timer, *, now: datetime) -> Timer:
    """PomodoroPaused -> PomodoroRunning, or BreakPaused -> BreakRunning; no penalty for pausing."""
    _ensure_phase(timer, *_PAUSED_TO_RUNNING, action="resume")
    return replace(timer, phase=_PAUSED_TO_RUNNING[timer.phase], running_since=now)


def stop(timer: Timer, *, now: datetime) -> Timer:
    """PomodoroRunning|PomodoroPaused -> AskingToLog, freezing the exact stop instant."""
    _ensure_phase(timer, TimerPhase.POMODORO_RUNNING, TimerPhase.POMODORO_PAUSED, action="stop")
    return replace(
        timer,
        phase=TimerPhase.ASKING_TO_LOG,
        accumulated_active_seconds=_freeze_accumulated(timer, now),
        running_since=None,
        phase_ended_at=now,
    )


def log(timer: Timer) -> TimerUpdate:
    """AskingToLog -> Idle, persisting an interrupted Pomodoro.

    Reads `ended_at` from the `phase_ended_at` frozen by `stop()`, never from a
    fresh `now()` here. If the frozen active time rounds to 0s, this is a no-op
    discard (documented spec edge case): no `PomodoroDraft` is produced.
    """
    _ensure_phase(timer, TimerPhase.ASKING_TO_LOG, action="log")
    idle = Timer(user_id=timer.user_id, phase=TimerPhase.IDLE)
    if timer.accumulated_active_seconds == 0:
        return TimerUpdate(timer=idle)
    draft = PomodoroDraft(
        task_id=timer.task_id,  # type: ignore[arg-type]  # invariant: set by start()
        started_at=timer.phase_started_at,  # type: ignore[arg-type]  # invariant: set by start()
        ended_at=timer.phase_ended_at,  # type: ignore[arg-type]  # invariant: set by stop()
        duration_seconds=timer.accumulated_active_seconds,
        status=PomodoroStatus.INTERRUPTED_LOGGED,
    )
    return TimerUpdate(timer=idle, pomodoro=draft)


def discard(timer: Timer) -> Timer:
    """AskingToLog -> Idle, discarding the interrupted Pomodoro: no trace, ever."""
    _ensure_phase(timer, TimerPhase.ASKING_TO_LOG, action="discard")
    return Timer(user_id=timer.user_id, phase=TimerPhase.IDLE)


def start_break(timer: Timer, *, now: datetime, total_completed_pomodoros: int) -> Timer:
    """ReadyForNext -> BreakRunning; its kind is derived from the completed-Pomodoro count."""
    _ensure_phase(timer, TimerPhase.READY_FOR_NEXT, action="start-break")
    return replace(
        timer,
        phase=TimerPhase.BREAK_RUNNING,
        task_id=None,
        break_kind=derive_break_kind(total_completed_pomodoros),
        phase_started_at=now,
        accumulated_active_seconds=0,
        running_since=now,
        phase_ended_at=None,
    )


def skip_break(timer: Timer) -> Timer:
    """BreakRunning|BreakPaused -> Idle. Never sounds the Alarm (a frontend-only concern)."""
    _ensure_phase(timer, TimerPhase.BREAK_RUNNING, TimerPhase.BREAK_PAUSED, action="skip-break")
    return Timer(user_id=timer.user_id, phase=TimerPhase.IDLE)


def next_pomodoro(timer: Timer, *, now: datetime) -> Timer:
    """ReadyForNext -> PomodoroRunning, continuing the same Task without returning to the list."""
    _ensure_phase(timer, TimerPhase.READY_FOR_NEXT, action="next-pomodoro")
    return replace(
        timer,
        phase=TimerPhase.POMODORO_RUNNING,
        break_kind=None,
        phase_started_at=now,
        accumulated_active_seconds=0,
        running_since=now,
        phase_ended_at=None,
    )
