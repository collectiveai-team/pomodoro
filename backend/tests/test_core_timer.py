"""Tests for the Timer state machine in core/ (T6)."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from pomodoro.core.entities import BreakKind, PomodoroStatus, TaskId, Timer, TimerPhase, UserId
from pomodoro.core.errors import TimerActionNotAllowedError
from pomodoro.core.timer import (
    BREAK_LONG_SECONDS,
    BREAK_SHORT_SECONDS,
    POMODORO_SECONDS,
    derive_break_kind,
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

_USER = UserId(1)
_TASK = TaskId(1)
_EPOCH = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@dataclass
class FakeClock:
    """A `Clock` test double advanced by hand instead of sleeping real time."""

    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


def _idle_timer() -> Timer:
    return Timer(user_id=_USER, phase=TimerPhase.IDLE)


def _ready_for_next() -> Timer:
    return Timer(user_id=_USER, phase=TimerPhase.READY_FOR_NEXT, task_id=_TASK)


class TestStart:
    def test_starts_a_pomodoro_from_idle(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        assert timer.phase is TimerPhase.POMODORO_RUNNING
        assert timer.task_id == _TASK
        assert timer.phase_started_at == _EPOCH
        assert timer.running_since == _EPOCH
        assert timer.accumulated_active_seconds == 0
        assert timer.phase_ended_at is None


class TestPauseResumeAccounting:
    def test_pause_freezes_accumulated_active_seconds(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        clock.advance(600)
        paused = pause(timer, now=clock.now())
        assert paused.phase is TimerPhase.POMODORO_PAUSED
        assert paused.accumulated_active_seconds == 600
        assert paused.running_since is None

    def test_time_spent_paused_never_accrues(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        clock.advance(600)
        paused = pause(timer, now=clock.now())
        clock.advance(300)  # time passes while paused; must not count
        resumed = resume(paused, now=clock.now())
        assert resumed.phase is TimerPhase.POMODORO_RUNNING
        assert resumed.accumulated_active_seconds == 600
        assert resumed.running_since == clock.now()

    def test_resumed_pomodoro_keeps_accruing_from_its_frozen_total(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        clock.advance(600)
        paused = pause(timer, now=clock.now())
        clock.advance(300)
        resumed = resume(paused, now=clock.now())
        clock.advance(600)  # 600 (frozen) + 600 (resumed) = 1200s, short of 1500s
        result = settle(resumed, clock.now())
        assert result.timer.phase is TimerPhase.POMODORO_RUNNING
        assert result.pomodoro is None

    def test_break_pause_resume_also_freezes_accumulated_active_seconds(self) -> None:
        clock = FakeClock(_EPOCH)
        running = start_break(_ready_for_next(), now=clock.now(), total_completed_pomodoros=1)
        clock.advance(120)
        paused = pause(running, now=clock.now())
        assert paused.phase is TimerPhase.BREAK_PAUSED
        assert paused.accumulated_active_seconds == 120


class TestStopLogDiscard:
    def test_stop_moves_to_asking_to_log_and_freezes_the_stop_instant(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        clock.advance(600)
        stopped = stop(timer, now=clock.now())
        assert stopped.phase is TimerPhase.ASKING_TO_LOG
        assert stopped.accumulated_active_seconds == 600
        assert stopped.phase_ended_at == clock.now()
        assert stopped.running_since is None

    def test_stop_from_paused_keeps_the_already_frozen_accumulated_seconds(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        clock.advance(600)
        paused = pause(timer, now=clock.now())
        clock.advance(300)  # paused: must not add to the frozen total
        stopped = stop(paused, now=clock.now())
        assert stopped.accumulated_active_seconds == 600

    def test_log_persists_the_interrupted_pomodoro_with_the_frozen_stop_instant(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        clock.advance(600)
        stopped = stop(timer, now=clock.now())
        clock.advance(3600)  # log() called an hour after stop(): must not use this "now"
        result = log(stopped)
        assert result.timer == Timer(user_id=_USER, phase=TimerPhase.IDLE)
        assert result.pomodoro is not None
        assert result.pomodoro.task_id == _TASK
        assert result.pomodoro.started_at == _EPOCH
        assert result.pomodoro.ended_at == _EPOCH + timedelta(seconds=600)
        assert result.pomodoro.ended_at != clock.now()
        assert result.pomodoro.duration_seconds == 600
        assert result.pomodoro.status is PomodoroStatus.INTERRUPTED_LOGGED

    def test_discard_leaves_no_trace(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        clock.advance(600)
        stopped = stop(timer, now=clock.now())
        assert discard(stopped) == Timer(user_id=_USER, phase=TimerPhase.IDLE)

    def test_log_with_zero_active_seconds_is_a_noop_discard(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        stopped = stop(timer, now=clock.now())  # stopped immediately: 0s active
        result = log(stopped)
        assert result.pomodoro is None
        assert result.timer == Timer(user_id=_USER, phase=TimerPhase.IDLE)

    def test_log_with_sub_second_active_time_rounding_to_zero_is_a_noop_discard(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        clock.advance(0.4)  # rounds to 0 whole seconds
        stopped = stop(timer, now=clock.now())
        result = log(stopped)
        assert result.pomodoro is None


class TestLazyCompletionWhileClosed:
    def test_settle_completes_a_pomodoro_at_the_exact_instant_it_ran_out(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        exact_deadline = _EPOCH + timedelta(seconds=POMODORO_SECONDS)
        clock.advance(3600 * 5)  # "app closed" for hours, long past the 25 min mark
        result = settle(timer, clock.now())
        assert result.timer.phase is TimerPhase.READY_FOR_NEXT
        assert result.timer.task_id == _TASK  # kept, for "otro Pomodoro"
        assert result.timer.phase_ended_at == exact_deadline
        assert result.pomodoro is not None
        assert result.pomodoro.ended_at == exact_deadline
        assert result.pomodoro.ended_at != clock.now()
        assert result.pomodoro.started_at == _EPOCH
        assert result.pomodoro.duration_seconds == POMODORO_SECONDS
        assert result.pomodoro.status is PomodoroStatus.COMPLETED

    def test_settle_does_not_complete_a_pomodoro_before_its_deadline(self) -> None:
        clock = FakeClock(_EPOCH)
        timer = start(_idle_timer(), task_id=_TASK, now=clock.now())
        clock.advance(POMODORO_SECONDS - 1)
        result = settle(timer, clock.now())
        assert result.timer == timer
        assert result.pomodoro is None

    def test_settle_completes_a_break_to_idle_at_the_exact_instant_it_ran_out(self) -> None:
        clock = FakeClock(_EPOCH)
        running = start_break(_ready_for_next(), now=clock.now(), total_completed_pomodoros=1)
        clock.advance(3600)  # "app closed" well past the short Break's 5 minutes
        result = settle(running, clock.now())
        assert result.timer == Timer(user_id=_USER, phase=TimerPhase.IDLE)
        assert result.pomodoro is None

    def test_settle_is_a_passthrough_for_a_break_still_running(self) -> None:
        clock = FakeClock(_EPOCH)
        running = start_break(_ready_for_next(), now=clock.now(), total_completed_pomodoros=5)
        clock.advance(BREAK_LONG_SECONDS - 1)
        result = settle(running, clock.now())
        assert result.timer == running
        assert result.pomodoro is None

    @pytest.mark.parametrize(
        "phase",
        [
            TimerPhase.IDLE,
            TimerPhase.POMODORO_PAUSED,
            TimerPhase.ASKING_TO_LOG,
            TimerPhase.BREAK_PAUSED,
            TimerPhase.READY_FOR_NEXT,
        ],
    )
    def test_settle_is_a_passthrough_for_phases_with_no_running_deadline(
        self, phase: TimerPhase
    ) -> None:
        timer = Timer(user_id=_USER, phase=phase)
        result = settle(timer, _EPOCH + timedelta(days=1))
        assert result.timer == timer
        assert result.pomodoro is None


class TestBreakCadence:
    @pytest.mark.parametrize(
        ("completed_count", "expected_kind"),
        [
            (1, BreakKind.SHORT),
            (2, BreakKind.SHORT),
            (3, BreakKind.SHORT),
            (4, BreakKind.SHORT),
            (5, BreakKind.LONG),
            (6, BreakKind.SHORT),
            (9, BreakKind.SHORT),
            (10, BreakKind.LONG),
            (15, BreakKind.LONG),
        ],
    )
    def test_derive_break_kind_every_5th_completed_pomodoro_is_long(
        self, completed_count: int, expected_kind: BreakKind
    ) -> None:
        assert derive_break_kind(completed_count) is expected_kind

    def test_start_break_uses_the_derived_kind_and_clears_the_task(self) -> None:
        clock = FakeClock(_EPOCH)
        running = start_break(_ready_for_next(), now=clock.now(), total_completed_pomodoros=5)
        assert running.phase is TimerPhase.BREAK_RUNNING
        assert running.break_kind is BreakKind.LONG
        assert running.task_id is None  # Break time never belongs to any Task
        assert running.accumulated_active_seconds == 0
        assert running.running_since == _EPOCH

    def test_a_short_break_settles_to_idle_after_its_own_shorter_duration(self) -> None:
        clock = FakeClock(_EPOCH)
        running = start_break(_ready_for_next(), now=clock.now(), total_completed_pomodoros=1)
        clock.advance(BREAK_SHORT_SECONDS)
        result = settle(running, clock.now())
        assert result.timer.phase is TimerPhase.IDLE


class TestSkipAndNextPomodoro:
    def test_skip_break_goes_straight_to_idle(self) -> None:
        clock = FakeClock(_EPOCH)
        running = start_break(_ready_for_next(), now=clock.now(), total_completed_pomodoros=1)
        assert skip_break(running) == Timer(user_id=_USER, phase=TimerPhase.IDLE)

    def test_skip_break_also_works_while_paused(self) -> None:
        clock = FakeClock(_EPOCH)
        running = start_break(_ready_for_next(), now=clock.now(), total_completed_pomodoros=1)
        paused = pause(running, now=clock.now())
        assert skip_break(paused) == Timer(user_id=_USER, phase=TimerPhase.IDLE)

    def test_next_pomodoro_continues_the_same_task_without_returning_to_the_list(self) -> None:
        clock = FakeClock(_EPOCH)
        ready = Timer(
            user_id=_USER,
            phase=TimerPhase.READY_FOR_NEXT,
            task_id=_TASK,
            accumulated_active_seconds=POMODORO_SECONDS,
            phase_ended_at=_EPOCH,
        )
        clock.advance(5)
        running = next_pomodoro(ready, now=clock.now())
        assert running.phase is TimerPhase.POMODORO_RUNNING
        assert running.task_id == _TASK
        assert running.phase_started_at == clock.now()
        assert running.accumulated_active_seconds == 0
        assert running.running_since == clock.now()


_ACTIONS = {
    "start": lambda timer, now: start(timer, task_id=_TASK, now=now),
    "pause": lambda timer, now: pause(timer, now=now),
    "resume": lambda timer, now: resume(timer, now=now),
    "stop": lambda timer, now: stop(timer, now=now),
    "log": lambda timer, now: log(timer),
    "discard": lambda timer, now: discard(timer),
    "start_break": lambda timer, now: start_break(timer, now=now, total_completed_pomodoros=1),
    "skip_break": lambda timer, now: skip_break(timer),
    "next_pomodoro": lambda timer, now: next_pomodoro(timer, now=now),
}

_ALLOWED_PHASES: dict[str, frozenset[TimerPhase]] = {
    "start": frozenset({TimerPhase.IDLE}),
    "pause": frozenset({TimerPhase.POMODORO_RUNNING, TimerPhase.BREAK_RUNNING}),
    "resume": frozenset({TimerPhase.POMODORO_PAUSED, TimerPhase.BREAK_PAUSED}),
    "stop": frozenset({TimerPhase.POMODORO_RUNNING, TimerPhase.POMODORO_PAUSED}),
    "log": frozenset({TimerPhase.ASKING_TO_LOG}),
    "discard": frozenset({TimerPhase.ASKING_TO_LOG}),
    "start_break": frozenset({TimerPhase.READY_FOR_NEXT}),
    "skip_break": frozenset({TimerPhase.BREAK_RUNNING, TimerPhase.BREAK_PAUSED}),
    "next_pomodoro": frozenset({TimerPhase.READY_FOR_NEXT}),
}

_INVALID_ACTION_PHASE_PAIRS = [
    (action, phase)
    for action, phase in itertools.product(_ACTIONS, TimerPhase)
    if phase not in _ALLOWED_PHASES[action]
]


class TestInvalidActionsRaiseWithTheCurrentTimer:
    @pytest.mark.parametrize(("action", "phase"), _INVALID_ACTION_PHASE_PAIRS)
    def test_every_invalid_action_phase_combination_raises(
        self, action: str, phase: TimerPhase
    ) -> None:
        timer = Timer(user_id=_USER, phase=phase)
        with pytest.raises(TimerActionNotAllowedError) as excinfo:
            _ACTIONS[action](timer, _EPOCH)
        assert excinfo.value.timer == timer

    def test_error_names_the_rejected_action(self) -> None:
        timer = Timer(user_id=_USER, phase=TimerPhase.IDLE)
        with pytest.raises(TimerActionNotAllowedError) as excinfo:
            pause(timer, now=_EPOCH)
        assert excinfo.value.action == "pause"
        assert excinfo.value.timer is timer
