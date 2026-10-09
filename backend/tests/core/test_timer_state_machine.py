"""Unit tests for the pure Timer state machine (ADR-0003)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from pomodoro.core.tasks import TaskId
from pomodoro.core.timer import (
    BREAK_LONG_SECONDS,
    BREAK_SHORT_SECONDS,
    POMODORO_SECONDS,
    BreakKind,
    InvalidTimerTransitionError,
    PomodoroStatus,
    Timer,
    TimerPhase,
    break_kind_for_completed_pomodoros,
    discard,
    log,
    next_pomodoro,
    pause,
    resume,
    settle,
    skip_break,
    start,
    start_break,
    stop,
)

pytestmark = pytest.mark.unit

TASK_ID = TaskId(UUID(int=1))
NOW = datetime(2026, 1, 1, tzinfo=UTC)

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class FakeClock:
    """A hand-advanced Clock adapter; no test relies on wall-clock time."""

    current: datetime

    def now(self) -> datetime:
        """Return the deterministic current time."""
        return self.current

    def advance(self, seconds: int) -> None:
        """Advance the fake clock by a whole number of seconds."""
        self.current += timedelta(seconds=seconds)


def _clock() -> FakeClock:
    return FakeClock(NOW.replace(hour=9))


def test_pause_and_resume_count_only_active_pomodoro_time() -> None:
    clock = _clock()
    timer = start(Timer(), task_id=TASK_ID, now=clock.now())
    clock.advance(600)

    paused = pause(timer, now=clock.now())
    clock.advance(300)
    resumed = resume(paused, now=clock.now())
    clock.advance(899)

    before_deadline = settle(resumed, now=clock.now())

    assert before_deadline.completed_pomodoro is None
    assert before_deadline.timer.phase is TimerPhase.POMODORO_RUNNING
    clock.advance(1)
    completed = settle(before_deadline.timer, now=clock.now())
    assert completed.timer.phase is TimerPhase.READY_FOR_NEXT
    assert completed.completed_pomodoro is not None
    assert completed.completed_pomodoro.duration_seconds == POMODORO_SECONDS


def test_settle_records_the_exact_pomodoro_deadline_after_a_late_read() -> None:
    clock = _clock()
    timer = start(Timer(), task_id=TASK_ID, now=clock.now())
    clock.advance(POMODORO_SECONDS + 60)

    result = settle(timer, now=clock.now())

    assert result.timer.phase is TimerPhase.READY_FOR_NEXT
    assert result.timer.running_since is None
    assert result.timer.accumulated_active_seconds == POMODORO_SECONDS
    assert result.completed_pomodoro is not None
    assert result.completed_pomodoro.status is PomodoroStatus.COMPLETED
    assert result.completed_pomodoro.started_at == NOW.replace(hour=9)
    assert result.completed_pomodoro.ended_at == NOW.replace(hour=9, minute=25)


def test_stopped_pomodoro_can_be_logged_without_offering_a_break() -> None:
    clock = _clock()
    timer = start(Timer(), task_id=TASK_ID, now=clock.now())
    clock.advance(420)
    asking_to_log = stop(timer, now=clock.now())

    assert asking_to_log.phase is TimerPhase.ASKING_TO_LOG
    result = log(asking_to_log, now=clock.now())

    assert result.pomodoro.status is PomodoroStatus.INTERRUPTED_LOGGED
    assert result.pomodoro.duration_seconds == 420
    assert result.timer.phase is TimerPhase.IDLE
    assert result.timer.task_id is None
    assert result.timer.break_kind is None


def test_stopped_pomodoro_can_be_discarded_without_offering_a_break() -> None:
    clock = _clock()
    timer = start(Timer(), task_id=TASK_ID, now=clock.now())
    clock.advance(420)

    final_timer = discard(stop(timer, now=clock.now()))

    assert final_timer.phase is TimerPhase.IDLE
    assert final_timer.task_id is None
    assert final_timer.break_kind is None


def test_every_fifth_completed_pomodoro_uses_a_long_break() -> None:
    clock = _clock()
    ready = Timer(phase=TimerPhase.READY_FOR_NEXT, task_id=TASK_ID)

    short_break = start_break(ready, now=clock.now(), completed_pomodoro_count=4)
    long_break = start_break(ready, now=clock.now(), completed_pomodoro_count=5)

    assert break_kind_for_completed_pomodoros(4) is BreakKind.SHORT
    assert break_kind_for_completed_pomodoros(5) is BreakKind.LONG
    assert short_break.break_kind is BreakKind.SHORT
    assert long_break.break_kind is BreakKind.LONG
    assert BREAK_SHORT_SECONDS == 300
    assert BREAK_LONG_SECONDS == 600


def test_natural_break_completion_returns_to_idle() -> None:
    clock = _clock()
    ready = Timer(phase=TimerPhase.READY_FOR_NEXT, task_id=TASK_ID)
    timer = start_break(ready, now=clock.now(), completed_pomodoro_count=1)
    clock.advance(BREAK_SHORT_SECONDS)

    result = settle(timer, now=clock.now())

    assert result.timer == Timer()
    assert result.completed_pomodoro is None


def test_break_can_be_paused_resumed_and_skipped() -> None:
    clock = _clock()
    ready = Timer(phase=TimerPhase.READY_FOR_NEXT, task_id=TASK_ID)
    timer = start_break(ready, now=clock.now(), completed_pomodoro_count=1)
    clock.advance(120)

    paused = pause(timer, now=clock.now())
    clock.advance(120)
    resumed = resume(paused, now=clock.now())
    final_timer = skip_break(resumed)

    assert paused.accumulated_active_seconds == 120
    assert resumed.phase is TimerPhase.BREAK_RUNNING
    assert final_timer == Timer()


def test_ready_timer_starts_another_pomodoro_for_the_same_task() -> None:
    clock = _clock()
    ready = Timer(phase=TimerPhase.READY_FOR_NEXT, task_id=TASK_ID)

    timer = next_pomodoro(ready, now=clock.now())

    assert timer.phase is TimerPhase.POMODORO_RUNNING
    assert timer.task_id == TASK_ID
    assert timer.break_kind is None
    assert timer.accumulated_active_seconds == 0
    assert timer.running_since == clock.now()


@pytest.mark.parametrize(
    ("action", "timer"),
    [
        (partial(start, task_id=TASK_ID, now=NOW), Timer(phase=TimerPhase.POMODORO_PAUSED)),
        (partial(pause, now=NOW), Timer()),
        (partial(resume, now=NOW), Timer()),
        (partial(stop, now=NOW), Timer()),
        (partial(log, now=NOW), Timer()),
        (discard, Timer()),
        (partial(start_break, now=NOW, completed_pomodoro_count=1), Timer()),
        (skip_break, Timer()),
        (partial(next_pomodoro, now=NOW), Timer()),
    ],
)
def test_actions_reject_non_matching_timer_phases(
    action: Callable[[Timer], object], timer: Timer
) -> None:
    with pytest.raises(InvalidTimerTransitionError):
        action(timer)
