"""Pure Timer state machine and lazy settlement rules (ADR-0003)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pomodoro.core.tasks import TaskId

POMODORO_SECONDS = 25 * 60
BREAK_SHORT_SECONDS = 5 * 60
BREAK_LONG_SECONDS = 10 * 60


class TimerPhase(StrEnum):
    """The mutually exclusive states of a User's live Timer."""

    IDLE = "Idle"
    POMODORO_RUNNING = "PomodoroRunning"
    POMODORO_PAUSED = "PomodoroPaused"
    ASKING_TO_LOG = "AskingToLog"
    BREAK_RUNNING = "BreakRunning"
    BREAK_PAUSED = "BreakPaused"
    READY_FOR_NEXT = "ReadyForNext"


class BreakKind(StrEnum):
    """The two fixed-duration Break variants."""

    SHORT = "short"
    LONG = "long"


class PomodoroStatus(StrEnum):
    """The only two kinds of Pomodoro that are recorded."""

    COMPLETED = "completed"
    INTERRUPTED_LOGGED = "interrupted_logged"


class InvalidTimerTransitionError(ValueError):
    """Raised when an action does not apply to the Timer's current phase."""


@dataclass(frozen=True, slots=True)
class Timer:
    """A User's live Timer state, scoped by its persistence adapter to that User."""

    phase: TimerPhase = TimerPhase.IDLE
    task_id: TaskId | None = None
    break_kind: BreakKind | None = None
    phase_started_at: datetime | None = None
    accumulated_active_seconds: int = 0
    running_since: datetime | None = None


@dataclass(frozen=True, slots=True)
class Pomodoro:
    """A completed or deliberately logged interrupted Pomodoro ready to persist."""

    task_id: TaskId
    started_at: datetime
    ended_at: datetime
    duration_seconds: int
    status: PomodoroStatus


@dataclass(frozen=True, slots=True)
class TimerSettlement:
    """The state after lazy settlement and an optional newly completed Pomodoro."""

    timer: Timer
    completed_pomodoro: Pomodoro | None = None


@dataclass(frozen=True, slots=True)
class LoggedPomodoro:
    """The idle Timer and interrupted Pomodoro emitted by the log transition."""

    timer: Timer
    pomodoro: Pomodoro


def active_seconds(timer: Timer, now: datetime) -> int:
    """Return elapsed active seconds, excluding any paused interval."""
    if timer.running_since is None:
        return timer.accumulated_active_seconds
    elapsed = int((now - timer.running_since).total_seconds())
    if elapsed < 0:
        raise ValueError("Timer cannot be evaluated before it started running.")
    return timer.accumulated_active_seconds + elapsed


def break_kind_for_completed_pomodoros(completed_pomodoro_count: int) -> BreakKind:
    """Return the Break kind due after this total number of completed Pomodoros."""
    if completed_pomodoro_count < 0:
        raise ValueError("Completed Pomodoro count cannot be negative.")
    if completed_pomodoro_count and completed_pomodoro_count % 5 == 0:
        return BreakKind.LONG
    return BreakKind.SHORT


def break_duration_seconds(break_kind: BreakKind) -> int:
    """Return the fixed duration for `break_kind`."""
    if break_kind is BreakKind.LONG:
        return BREAK_LONG_SECONDS
    return BREAK_SHORT_SECONDS


def settle(timer: Timer, now: datetime) -> TimerSettlement:
    """Lazily complete an elapsed running phase at its exact deadline, if any."""
    is_completed_pomodoro = (
        timer.phase is TimerPhase.POMODORO_RUNNING
        and active_seconds(timer, now) >= POMODORO_SECONDS
    )
    if is_completed_pomodoro:
        return _settle_completed_pomodoro(timer)
    if timer.phase is TimerPhase.BREAK_RUNNING and _break_is_complete(timer, now):
        return TimerSettlement(timer=Timer())
    return TimerSettlement(timer=timer)


def start(timer: Timer, *, task_id: TaskId, now: datetime) -> Timer:
    """Start a new Pomodoro for `task_id` from Idle."""
    _require_phase(timer, "start", TimerPhase.IDLE)
    return Timer(
        phase=TimerPhase.POMODORO_RUNNING,
        task_id=task_id,
        phase_started_at=now,
        running_since=now,
    )


def pause(timer: Timer, *, now: datetime) -> Timer:
    """Pause a running Pomodoro or Break while preserving active time."""
    _require_phase(timer, "pause", TimerPhase.POMODORO_RUNNING, TimerPhase.BREAK_RUNNING)
    paused_phase = (
        TimerPhase.POMODORO_PAUSED
        if timer.phase is TimerPhase.POMODORO_RUNNING
        else TimerPhase.BREAK_PAUSED
    )
    return replace(
        timer,
        phase=paused_phase,
        accumulated_active_seconds=active_seconds(timer, now),
        running_since=None,
    )


def resume(timer: Timer, *, now: datetime) -> Timer:
    """Resume a paused Pomodoro or Break without counting its paused interval."""
    _require_phase(timer, "resume", TimerPhase.POMODORO_PAUSED, TimerPhase.BREAK_PAUSED)
    running_phase = (
        TimerPhase.POMODORO_RUNNING
        if timer.phase is TimerPhase.POMODORO_PAUSED
        else TimerPhase.BREAK_RUNNING
    )
    return replace(timer, phase=running_phase, running_since=now)


def stop(timer: Timer, *, now: datetime) -> Timer:
    """Stop a Pomodoro and ask whether its elapsed active time should be logged."""
    _require_phase(timer, "stop", TimerPhase.POMODORO_RUNNING, TimerPhase.POMODORO_PAUSED)
    accumulated = active_seconds(timer, now)
    return replace(
        timer,
        phase=TimerPhase.ASKING_TO_LOG,
        accumulated_active_seconds=accumulated,
        running_since=None,
    )


def log(timer: Timer, *, now: datetime) -> LoggedPomodoro:
    """Log an interrupted Pomodoro, then return the Timer to Idle without a Break."""
    _require_phase(timer, "log", TimerPhase.ASKING_TO_LOG)
    return LoggedPomodoro(
        timer=Timer(),
        pomodoro=Pomodoro(
            task_id=_task_id(timer),
            started_at=_phase_started_at(timer),
            ended_at=now,
            duration_seconds=timer.accumulated_active_seconds,
            status=PomodoroStatus.INTERRUPTED_LOGGED,
        ),
    )


def discard(timer: Timer) -> Timer:
    """Discard an interrupted Pomodoro and return to Idle without recording it or a Break."""
    _require_phase(timer, "discard", TimerPhase.ASKING_TO_LOG)
    return Timer()


def start_break(timer: Timer, *, now: datetime, completed_pomodoro_count: int) -> Timer:
    """Start the short or long Break due after the User's completed Pomodoro count."""
    _require_phase(timer, "start-break", TimerPhase.READY_FOR_NEXT)
    return Timer(
        phase=TimerPhase.BREAK_RUNNING,
        task_id=_task_id(timer),
        break_kind=break_kind_for_completed_pomodoros(completed_pomodoro_count),
        phase_started_at=now,
        running_since=now,
    )


def skip_break(timer: Timer) -> Timer:
    """Skip a running or paused Break and return to Idle without a completion event."""
    _require_phase(timer, "skip-break", TimerPhase.BREAK_RUNNING, TimerPhase.BREAK_PAUSED)
    return Timer()


def next_pomodoro(timer: Timer, *, now: datetime) -> Timer:
    """Start another Pomodoro for the Task retained after a completion."""
    _require_phase(timer, "next-pomodoro", TimerPhase.READY_FOR_NEXT)
    return Timer(
        phase=TimerPhase.POMODORO_RUNNING,
        task_id=_task_id(timer),
        phase_started_at=now,
        running_since=now,
    )


def _settle_completed_pomodoro(timer: Timer) -> TimerSettlement:
    """Build the exact completion record and expose the Break-ready Timer state."""
    task_id = _task_id(timer)
    phase_started_at = _phase_started_at(timer)
    running_since = _running_since(timer)
    ended_at = running_since + timedelta(
        seconds=POMODORO_SECONDS - timer.accumulated_active_seconds
    )
    return TimerSettlement(
        timer=replace(
            timer,
            phase=TimerPhase.READY_FOR_NEXT,
            accumulated_active_seconds=POMODORO_SECONDS,
            running_since=None,
        ),
        completed_pomodoro=Pomodoro(
            task_id=task_id,
            started_at=phase_started_at,
            ended_at=ended_at,
            duration_seconds=POMODORO_SECONDS,
            status=PomodoroStatus.COMPLETED,
        ),
    )


def _break_is_complete(timer: Timer, now: datetime) -> bool:
    """Whether `timer`'s running Break has reached its fixed active duration."""
    break_kind = timer.break_kind
    if break_kind is None:
        raise ValueError("A running Break must have a Break kind.")
    return active_seconds(timer, now) >= break_duration_seconds(break_kind)


def _require_phase(timer: Timer, action: str, *expected_phases: TimerPhase) -> None:
    """Raise the domain error unless `timer` currently admits `action`."""
    if timer.phase not in expected_phases:
        expected = ", ".join(phase.value for phase in expected_phases)
        raise InvalidTimerTransitionError(
            f"Cannot {action} while Timer is {timer.phase.value}; expected {expected}."
        )


def _task_id(timer: Timer) -> TaskId:
    """Return the Task held by an in-progress Timer state."""
    if timer.task_id is None:
        raise ValueError(f"Timer phase {timer.phase.value} requires a Task.")
    return timer.task_id


def _phase_started_at(timer: Timer) -> datetime:
    """Return the timestamp that began the current Pomodoro or Break phase family."""
    if timer.phase_started_at is None:
        raise ValueError(f"Timer phase {timer.phase.value} requires a start timestamp.")
    return timer.phase_started_at


def _running_since(timer: Timer) -> datetime:
    """Return the timestamp at which the currently running phase resumed."""
    if timer.running_since is None:
        raise ValueError(f"Timer phase {timer.phase.value} requires a running timestamp.")
    return timer.running_since
