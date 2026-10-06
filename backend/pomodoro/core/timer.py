"""The Timer value object: phase transitions, lazy settle, and break cadence.

Pure core: no FastAPI/SQLModel/Pydantic imports. `now` is always supplied by
the caller (sourced from the injectable `Clock`), never read from a wall
clock here. There are no background jobs: `settle()` is the only mechanism
that resolves a phase that has already elapsed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, timedelta
from enum import Enum
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from pomodoro.core.entities import Pomodoro, PomodoroId, PomodoroStatus
from pomodoro.core.errors import InvalidTimerActionError, TaskNotActiveError

if TYPE_CHECKING:
    from datetime import datetime

    from pomodoro.core.entities import Task, TaskId, UserId
    from pomodoro.core.repositories import PomodoroRepository, TimerRepository

POMODORO_SECONDS = 25 * 60
SHORT_BREAK_SECONDS = 5 * 60
LONG_BREAK_SECONDS = 10 * 60
LONG_BREAK_EVERY = 5


class TimerPhase(Enum):
    """Where a User's single live Timer currently stands."""

    IDLE = "idle"
    POMODORO_RUNNING = "pomodoro_running"
    POMODORO_PAUSED = "pomodoro_paused"
    ASKING_TO_LOG = "asking_to_log"
    BREAK_RUNNING = "break_running"
    BREAK_PAUSED = "break_paused"
    READY_FOR_NEXT = "ready_for_next"


class BreakKind(Enum):
    """Which Break duration applies: short (5 min) or long (10 min)."""

    SHORT = "short"
    LONG = "long"


@dataclass(frozen=True)
class Timer:
    """A User's single live Pomodoro/Break state.

    `phase_started_at` is fixed at the start of the current Pomodoro/Break
    (pause/resume never change it) so it can supply a persisted Pomodoro's
    `started_at`. `running_since` is `None` whenever the phase isn't running
    (paused, or a phase with no notion of running at all).
    """

    user_id: UserId
    phase: TimerPhase
    task_id: TaskId | None
    break_kind: BreakKind | None
    phase_started_at: datetime | None
    accumulated_active_seconds: int
    running_since: datetime | None
    phase_ended_at: datetime | None = None


@dataclass(frozen=True)
class SettleResult:
    """The outcome of resolving any phase that had already elapsed."""

    timer: Timer
    completed_pomodoro: Pomodoro | None = None


@dataclass(frozen=True)
class LogResult:
    """The outcome of confirming a stopped Pomodoro (or its effective discard)."""

    timer: Timer
    pomodoro: Pomodoro | None = None


def idle_timer(user_id: UserId) -> Timer:
    """Build a fresh, Idle Timer for a User with no Timer row yet."""
    return Timer(
        user_id=user_id,
        phase=TimerPhase.IDLE,
        task_id=None,
        break_kind=None,
        phase_started_at=None,
        accumulated_active_seconds=0,
        running_since=None,
        phase_ended_at=None,
    )


def active_seconds(timer: Timer, now: datetime) -> int:
    """Return the Timer's active time in seconds as of `now`."""
    if timer.running_since is None:
        return timer.accumulated_active_seconds
    return timer.accumulated_active_seconds + _elapsed_seconds(timer.running_since, now)


def _elapsed_seconds(since: datetime, now: datetime) -> int:
    return round((now - since).total_seconds())


def break_duration_seconds(break_kind: BreakKind) -> int:
    """Return the fixed duration of a Break kind, in seconds."""
    return LONG_BREAK_SECONDS if break_kind is BreakKind.LONG else SHORT_BREAK_SECONDS


def determine_break_kind(completed_count: int) -> BreakKind:
    """Return Long every `LONG_BREAK_EVERY`th completed Pomodoro, else Short."""
    return BreakKind.LONG if completed_count % LONG_BREAK_EVERY == 0 else BreakKind.SHORT


def _require_phase(timer: Timer, *allowed: TimerPhase) -> None:
    if timer.phase not in allowed:
        raise InvalidTimerActionError


def _idle(timer: Timer) -> Timer:
    return replace(
        timer,
        phase=TimerPhase.IDLE,
        task_id=None,
        break_kind=None,
        phase_started_at=None,
        accumulated_active_seconds=0,
        running_since=None,
        phase_ended_at=None,
    )


def settle(timer: Timer, now: datetime) -> SettleResult:
    """Resolve a phase that has already elapsed, to the exact instant it did.

    A no-op for every phase except `PomodoroRunning` (25 active minutes) and
    `BreakRunning` (its fixed duration). Meant to run before every read/action
    so an elapsed phase is caught even if the app was closed when it happened.
    """
    if timer.phase is TimerPhase.POMODORO_RUNNING:
        return _settle_pomodoro(timer, now)
    if timer.phase is TimerPhase.BREAK_RUNNING:
        return _settle_break(timer, now)
    return SettleResult(timer=timer)


MAX_SETTLE_CAS_ATTEMPTS = 5


def settle_and_persist(
    timer_repo: TimerRepository,
    pomodoro_repo: PomodoroRepository,
    user_id: UserId,
    now: datetime,
) -> Timer:
    """Lazily settle the User's stored Timer and persist any resulting side effects.

    Shared by `api.timer` (every route) and `api.tasks` (the in-progress-Task
    guard) so neither reimplements settle-then-persist against the stored row.
    """
    timer, _version = settle_and_persist_with_version(timer_repo, pomodoro_repo, user_id, now)
    return timer


def settle_and_persist_with_version(
    timer_repo: TimerRepository,
    pomodoro_repo: PomodoroRepository,
    user_id: UserId,
    now: datetime,
) -> tuple[Timer, int | None]:
    """Like `settle_and_persist`, also returning the stored row's version.

    Lets a caller that is about to persist a further change of its own (the
    `/log` route) chain a `save_if_unchanged` against the exact row this call
    observed, rather than racing a second, independent settle+persist.

    A completed/elapsed phase is persisted via a compare-and-swap write keyed
    on that version: when two callers observe the same elapsed Timer at once
    (the app's own concurrent `GET /api/timer` pair on mount, per stories
    64-68), only the one that wins the CAS inserts the completed Pomodoro; the
    other re-reads the now-settled row, finds nothing left to settle, and
    returns without persisting anything a second time.
    """
    for _ in range(MAX_SETTLE_CAS_ATTEMPTS):
        stored = timer_repo.get_with_version(user_id)
        timer, version = stored if stored is not None else (idle_timer(user_id), None)
        result = settle(timer, now)
        if result.timer == timer:
            return result.timer, version
        if timer_repo.save_if_unchanged(user_id, version, result.timer):
            if result.completed_pomodoro is not None:
                pomodoro_repo.add(result.completed_pomodoro)
            return result.timer, (0 if version is None else version + 1)
        # Another request settled or changed the Timer first; retry against
        # whatever it left behind rather than persisting a second time.
    stored = timer_repo.get_with_version(user_id)
    return stored if stored is not None else (idle_timer(user_id), None)


def _settle_pomodoro(timer: Timer, now: datetime) -> SettleResult:
    if active_seconds(timer, now) < POMODORO_SECONDS:
        return SettleResult(timer=timer)
    running_since = timer.running_since
    if running_since is None:
        raise AssertionError
    completed_at = running_since + timedelta(
        seconds=POMODORO_SECONDS - timer.accumulated_active_seconds
    )
    pomodoro = Pomodoro(
        id=PomodoroId(0),
        user_id=timer.user_id,
        task_id=timer.task_id,  # type: ignore[arg-type]
        started_at=timer.phase_started_at,  # type: ignore[arg-type]
        ended_at=completed_at,
        duration_seconds=POMODORO_SECONDS,
        status=PomodoroStatus.COMPLETED,
    )
    resolved = replace(
        timer,
        phase=TimerPhase.READY_FOR_NEXT,
        break_kind=None,
        phase_started_at=None,
        accumulated_active_seconds=0,
        running_since=None,
    )
    return SettleResult(timer=resolved, completed_pomodoro=pomodoro)


def _settle_break(timer: Timer, now: datetime) -> SettleResult:
    duration = break_duration_seconds(timer.break_kind)  # type: ignore[arg-type]
    if active_seconds(timer, now) < duration:
        return SettleResult(timer=timer)
    return SettleResult(timer=_idle(timer))


def start(timer: Timer, task_id: TaskId, now: datetime) -> Timer:
    """Idle + start(task) -> PomodoroRunning."""
    _require_phase(timer, TimerPhase.IDLE)
    return replace(
        timer,
        phase=TimerPhase.POMODORO_RUNNING,
        task_id=task_id,
        break_kind=None,
        phase_started_at=now,
        accumulated_active_seconds=0,
        running_since=now,
    )


def start_on_task(timer: Timer, task: Task, now: datetime) -> Timer:
    """Idle + start(task) -> PomodoroRunning, rejecting a Task that isn't Active."""
    if task.archived_at is not None:
        raise TaskNotActiveError
    return start(timer, task.id, now)


def pause(timer: Timer, now: datetime) -> Timer:
    """PomodoroRunning<->PomodoroPaused or BreakRunning<->BreakPaused (pause half)."""
    _require_phase(timer, TimerPhase.POMODORO_RUNNING, TimerPhase.BREAK_RUNNING)
    next_phase = (
        TimerPhase.POMODORO_PAUSED
        if timer.phase is TimerPhase.POMODORO_RUNNING
        else TimerPhase.BREAK_PAUSED
    )
    return replace(
        timer,
        phase=next_phase,
        accumulated_active_seconds=active_seconds(timer, now),
        running_since=None,
    )


def resume(timer: Timer, now: datetime) -> Timer:
    """PomodoroRunning<->PomodoroPaused or BreakRunning<->BreakPaused (resume half)."""
    _require_phase(timer, TimerPhase.POMODORO_PAUSED, TimerPhase.BREAK_PAUSED)
    next_phase = (
        TimerPhase.POMODORO_RUNNING
        if timer.phase is TimerPhase.POMODORO_PAUSED
        else TimerPhase.BREAK_RUNNING
    )
    return replace(timer, phase=next_phase, running_since=now)


def stop(timer: Timer, now: datetime) -> Timer:
    """PomodoroRunning|PomodoroPaused + stop -> AskingToLog.

    Records the real wall-clock stop instant in `phase_ended_at`: `log` (which
    may run arbitrarily later, after the User decides whether to log or
    discard) needs the actual end instant, not one re-derived from
    `phase_started_at + accumulated_active_seconds`, which silently excludes
    every paused gap and so misattributes a Pomodoro paused across local
    midnight to the wrong calendar day (story 80).
    """
    _require_phase(timer, TimerPhase.POMODORO_RUNNING, TimerPhase.POMODORO_PAUSED)
    return replace(
        timer,
        phase=TimerPhase.ASKING_TO_LOG,
        accumulated_active_seconds=active_seconds(timer, now),
        running_since=None,
        phase_ended_at=now,
    )


def _interrupted_ended_at(timer: Timer) -> datetime:
    """Return the stop instant of an AskingToLog Timer.

    Timers stopped before `phase_ended_at` existed carry NULL there (the
    migration adds the column without a backfill); fall back to the previous
    rule, start plus active time, rather than persisting a NULL `ended_at`.
    """
    if timer.phase_ended_at is not None:
        return timer.phase_ended_at
    return timer.phase_started_at + timedelta(seconds=timer.accumulated_active_seconds)  # type: ignore[operator]


def log(timer: Timer) -> LogResult:
    """AskingToLog + log -> Idle, persisting the real unpaused time.

    An active time that rounds to 0 seconds is treated as a discard: no
    Pomodoro is returned, matching the database's `duration_seconds > 0`
    constraint.
    """
    _require_phase(timer, TimerPhase.ASKING_TO_LOG)
    if timer.accumulated_active_seconds <= 0:
        return LogResult(timer=_idle(timer))
    pomodoro = Pomodoro(
        id=PomodoroId(0),
        user_id=timer.user_id,
        task_id=timer.task_id,  # type: ignore[arg-type]
        started_at=timer.phase_started_at,  # type: ignore[arg-type]
        ended_at=_interrupted_ended_at(timer),
        duration_seconds=timer.accumulated_active_seconds,
        status=PomodoroStatus.INTERRUPTED_LOGGED,
    )
    return LogResult(timer=_idle(timer), pomodoro=pomodoro)


def discard(timer: Timer) -> Timer:
    """AskingToLog + discard -> Idle, persisting nothing."""
    _require_phase(timer, TimerPhase.ASKING_TO_LOG)
    return _idle(timer)


def start_break(timer: Timer, now: datetime, completed_count: int) -> Timer:
    """ReadyForNext + start-break -> BreakRunning, short or long by cadence."""
    _require_phase(timer, TimerPhase.READY_FOR_NEXT)
    return replace(
        timer,
        phase=TimerPhase.BREAK_RUNNING,
        break_kind=determine_break_kind(completed_count),
        phase_started_at=now,
        accumulated_active_seconds=0,
        running_since=now,
    )


def skip_break(timer: Timer) -> Timer:
    """ReadyForNext|BreakRunning|BreakPaused + skip-break -> Idle, no Alarm."""
    _require_phase(
        timer, TimerPhase.READY_FOR_NEXT, TimerPhase.BREAK_RUNNING, TimerPhase.BREAK_PAUSED
    )
    return _idle(timer)


def next_pomodoro(timer: Timer, now: datetime) -> Timer:
    """ReadyForNext + next-pomodoro -> PomodoroRunning on the same Task."""
    _require_phase(timer, TimerPhase.READY_FOR_NEXT)
    return replace(
        timer,
        phase=TimerPhase.POMODORO_RUNNING,
        break_kind=None,
        phase_started_at=now,
        accumulated_active_seconds=0,
        running_since=now,
    )


def pomodoros_until_long_break(total_completed: int) -> int:
    """Return how many more completed Pomodoros are needed to earn the next long Break."""
    return LONG_BREAK_EVERY - (total_completed % LONG_BREAK_EVERY)


def local_day_bounds_utc(now: datetime, time_zone: str) -> tuple[datetime, datetime]:
    """Return the `[start, end)` UTC instants covering `now`'s local calendar day.

    Used for the day summary's "completed today" count: a Pomodoro belongs to
    the local day of its `ended_at`, per the User's `time_zone`, computed in
    Python with `zoneinfo` rather than any engine-specific SQL.
    """
    zone = ZoneInfo(time_zone)
    local_now = now.astimezone(zone)
    start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)
