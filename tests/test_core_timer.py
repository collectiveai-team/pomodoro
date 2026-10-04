"""Unit tests for the Timer state machine: transitions, settle, and break cadence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from pomodoro.core.entities import Pomodoro, PomodoroId, PomodoroStatus, TaskId, UserId
from pomodoro.core.errors import InvalidTimerActionError
from pomodoro.core.repositories import PomodoroRepository, TimerRepository
from pomodoro.core.timer import (
    POMODORO_SECONDS,
    SHORT_BREAK_SECONDS,
    BreakKind,
    Timer,
    TimerPhase,
    active_seconds,
    determine_break_kind,
    discard,
    idle_timer,
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

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
USER = UserId(1)
TASK = TaskId(1)


@dataclass
class FakeClock:
    """A `Clock` advanced by hand, standing in for the real wall clock in tests."""

    current: datetime = NOW

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> datetime:
        self.current += timedelta(seconds=seconds)
        return self.current


# --- active_seconds -----------------------------------------------------------


def test_active_seconds_when_running_adds_elapsed_time_since_running_since() -> None:
    timer = start(idle_timer(USER), TASK, NOW)
    assert active_seconds(timer, NOW + timedelta(seconds=90)) == 90


def test_active_seconds_when_paused_is_just_accumulated() -> None:
    clock = FakeClock()
    timer = start(idle_timer(USER), TASK, clock.now())
    clock.advance(100)
    paused = pause(timer, clock.now())
    clock.advance(500)  # elapses while paused; must not count
    assert active_seconds(paused, clock.now()) == 100


# --- start / pause / resume accounting -----------------------------------------


def test_start_from_idle_enters_pomodoro_running() -> None:
    timer = start(idle_timer(USER), TASK, NOW)
    assert timer.phase is TimerPhase.POMODORO_RUNNING
    assert timer.task_id == TASK
    assert timer.phase_started_at == NOW
    assert timer.running_since == NOW
    assert timer.accumulated_active_seconds == 0


def test_start_rejected_when_not_idle() -> None:
    timer = start(idle_timer(USER), TASK, NOW)
    with pytest.raises(InvalidTimerActionError):
        start(timer, TASK, NOW)


def test_pause_then_resume_accumulates_only_running_time() -> None:
    clock = FakeClock()
    timer = start(idle_timer(USER), TASK, clock.now())
    clock.advance(60)
    timer = pause(timer, clock.now())
    assert timer.phase is TimerPhase.POMODORO_PAUSED
    assert timer.accumulated_active_seconds == 60
    assert timer.running_since is None

    clock.advance(300)  # paused gap, must not count
    timer = resume(timer, clock.now())
    assert timer.phase is TimerPhase.POMODORO_RUNNING
    assert timer.running_since == clock.now()

    clock.advance(40)
    assert active_seconds(timer, clock.now()) == 100  # 60 + 40, gap excluded

    timer = pause(timer, clock.now())
    assert timer.accumulated_active_seconds == 100

    # phase_started_at must survive the whole pause/resume dance unchanged.
    assert timer.phase_started_at == NOW


def test_pause_rejected_when_idle() -> None:
    with pytest.raises(InvalidTimerActionError):
        pause(idle_timer(USER), NOW)


def test_resume_rejected_when_running() -> None:
    timer = start(idle_timer(USER), TASK, NOW)
    with pytest.raises(InvalidTimerActionError):
        resume(timer, NOW)


def test_pause_resume_also_applies_to_break_phases() -> None:
    clock = FakeClock()
    timer = start_break(_ready_for_next(), clock.now(), completed_count=1)
    assert timer.phase is TimerPhase.BREAK_RUNNING
    clock.advance(30)
    timer = pause(timer, clock.now())
    assert timer.phase is TimerPhase.BREAK_PAUSED
    assert timer.accumulated_active_seconds == 30
    timer = resume(timer, clock.now())
    assert timer.phase is TimerPhase.BREAK_RUNNING


# --- stop -> log / discard ------------------------------------------------------


def test_stop_moves_running_pomodoro_to_asking_to_log_freezing_active_time() -> None:
    clock = FakeClock()
    timer = start(idle_timer(USER), TASK, clock.now())
    clock.advance(42)
    timer = stop(timer, clock.now())
    assert timer.phase is TimerPhase.ASKING_TO_LOG
    assert timer.accumulated_active_seconds == 42
    assert timer.running_since is None


def test_stop_allowed_from_paused_pomodoro_too() -> None:
    clock = FakeClock()
    timer = start(idle_timer(USER), TASK, clock.now())
    clock.advance(20)
    timer = pause(timer, clock.now())
    clock.advance(999)  # paused gap, must not count
    timer = stop(timer, clock.now())
    assert timer.accumulated_active_seconds == 20


def test_stop_rejected_from_idle() -> None:
    with pytest.raises(InvalidTimerActionError):
        stop(idle_timer(USER), NOW)


def test_log_persists_interrupted_logged_with_real_unpaused_time() -> None:
    clock = FakeClock()
    timer = start(idle_timer(USER), TASK, clock.now())
    clock.advance(30)
    timer = pause(timer, clock.now())
    clock.advance(1000)  # paused gap must be excluded from the logged duration
    timer = resume(timer, clock.now())
    clock.advance(15)
    timer = stop(timer, clock.now())

    result = log(timer)

    assert result.timer.phase is TimerPhase.IDLE
    assert result.timer.task_id is None
    assert result.pomodoro is not None
    pomodoro = result.pomodoro
    assert pomodoro.user_id == USER
    assert pomodoro.task_id == TASK
    assert pomodoro.status is PomodoroStatus.INTERRUPTED_LOGGED
    assert pomodoro.duration_seconds == 45  # 30 + 15, excluding the paused gap
    assert pomodoro.started_at == NOW
    assert pomodoro.ended_at == NOW + timedelta(seconds=45)
    assert pomodoro.ended_at >= pomodoro.started_at


def test_log_with_zero_active_seconds_behaves_as_a_discard() -> None:
    timer = stop(start(idle_timer(USER), TASK, NOW), NOW)
    assert timer.accumulated_active_seconds == 0

    result = log(timer)

    assert result.pomodoro is None
    assert result.timer.phase is TimerPhase.IDLE


def test_discard_persists_nothing_and_returns_to_idle() -> None:
    clock = FakeClock()
    timer = start(idle_timer(USER), TASK, clock.now())
    clock.advance(500)
    timer = stop(timer, clock.now())

    result = discard(timer)

    assert result.phase is TimerPhase.IDLE
    assert result.task_id is None
    assert result.accumulated_active_seconds == 0


def test_log_and_discard_offer_no_break_either_way() -> None:
    """Both paths land directly on Idle; a Break is only ever offered from ReadyForNext."""
    stopped = stop(start(idle_timer(USER), TASK, NOW), NOW + timedelta(seconds=10))
    assert log(stopped).timer.phase is TimerPhase.IDLE
    assert discard(stopped).phase is TimerPhase.IDLE


def test_log_rejected_outside_asking_to_log() -> None:
    with pytest.raises(InvalidTimerActionError):
        log(idle_timer(USER))


def test_discard_rejected_outside_asking_to_log() -> None:
    with pytest.raises(InvalidTimerActionError):
        discard(idle_timer(USER))


# --- break cadence ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("completed_count", "expected"),
    [
        (1, BreakKind.SHORT),
        (4, BreakKind.SHORT),
        (5, BreakKind.LONG),
        (6, BreakKind.SHORT),
        (10, BreakKind.LONG),
    ],
)
def test_determine_break_kind_is_long_every_fifth_completion(
    completed_count: int, expected: BreakKind
) -> None:
    assert determine_break_kind(completed_count) is expected


def test_start_break_on_the_fifth_completion_is_long() -> None:
    timer = start_break(_ready_for_next(), NOW, completed_count=5)
    assert timer.phase is TimerPhase.BREAK_RUNNING
    assert timer.break_kind is BreakKind.LONG


def test_start_break_otherwise_is_short() -> None:
    timer = start_break(_ready_for_next(), NOW, completed_count=3)
    assert timer.break_kind is BreakKind.SHORT


def test_start_break_rejected_outside_ready_for_next() -> None:
    with pytest.raises(InvalidTimerActionError):
        start_break(idle_timer(USER), NOW, completed_count=1)


def test_skip_break_from_ready_for_next_goes_idle() -> None:
    timer = skip_break(_ready_for_next())
    assert timer.phase is TimerPhase.IDLE
    assert timer.task_id is None


def test_skip_break_from_running_or_paused_break_goes_idle() -> None:
    running = start_break(_ready_for_next(), NOW, completed_count=1)
    assert skip_break(running).phase is TimerPhase.IDLE
    paused = pause(running, NOW + timedelta(seconds=5))
    assert skip_break(paused).phase is TimerPhase.IDLE


def test_skip_break_rejected_while_a_pomodoro_is_running() -> None:
    timer = start(idle_timer(USER), TASK, NOW)
    with pytest.raises(InvalidTimerActionError):
        skip_break(timer)


def test_next_pomodoro_starts_a_new_pomodoro_on_the_same_task() -> None:
    clock = FakeClock()
    ready = _ready_for_next(task_id=TASK)
    clock.advance(10)
    timer = next_pomodoro(ready, clock.now())
    assert timer.phase is TimerPhase.POMODORO_RUNNING
    assert timer.task_id == TASK
    assert timer.phase_started_at == clock.now()
    assert timer.accumulated_active_seconds == 0


def test_next_pomodoro_rejected_outside_ready_for_next() -> None:
    with pytest.raises(InvalidTimerActionError):
        next_pomodoro(idle_timer(USER), NOW)


# --- settle: Pomodoro auto-completion -----------------------------------------


def test_settle_is_a_no_op_before_the_pomodoro_threshold() -> None:
    timer = start(idle_timer(USER), TASK, NOW)
    result = settle(timer, NOW + timedelta(minutes=10))
    assert result.timer == timer
    assert result.completed_pomodoro is None


def test_settle_auto_completes_a_pomodoro_at_exactly_25_active_minutes() -> None:
    timer = start(idle_timer(USER), TASK, NOW)
    result = settle(timer, NOW + timedelta(seconds=POMODORO_SECONDS))

    assert result.timer.phase is TimerPhase.READY_FOR_NEXT
    assert result.timer.task_id == TASK  # kept, so next-pomodoro can reuse it
    assert result.completed_pomodoro is not None
    pomodoro = result.completed_pomodoro
    assert pomodoro.status is PomodoroStatus.COMPLETED
    assert pomodoro.duration_seconds == POMODORO_SECONDS
    assert pomodoro.started_at == NOW
    assert pomodoro.ended_at == NOW + timedelta(seconds=POMODORO_SECONDS)


def test_settle_resolves_a_completion_that_happened_while_the_clock_ran_far_ahead() -> None:
    """The app was 'closed': the clock jumps straight past completion with no intermediate read."""
    timer = start(idle_timer(USER), TASK, NOW)
    much_later = NOW + timedelta(hours=6)

    result = settle(timer, much_later)

    assert result.completed_pomodoro is not None
    # ended_at is the exact instant it completed, not `much_later`.
    assert result.completed_pomodoro.ended_at == NOW + timedelta(seconds=POMODORO_SECONDS)
    assert result.timer.phase is TimerPhase.READY_FOR_NEXT


def test_settle_accounts_for_time_already_accumulated_before_the_current_run() -> None:
    clock = FakeClock()
    timer = start(idle_timer(USER), TASK, clock.now())
    clock.advance(1000)
    timer = pause(timer, clock.now())
    clock.advance(999)  # paused gap, excluded
    timer = resume(timer, clock.now())

    remaining = POMODORO_SECONDS - 1000
    result = settle(timer, clock.now() + timedelta(seconds=remaining))

    assert result.completed_pomodoro is not None
    assert result.completed_pomodoro.duration_seconds == POMODORO_SECONDS
    assert result.completed_pomodoro.ended_at == clock.now() + timedelta(seconds=remaining)


# --- settle: Break elapsing on its own -------------------------------------------


def test_settle_is_a_no_op_before_the_break_elapses() -> None:
    timer = start_break(_ready_for_next(), NOW, completed_count=1)
    result = settle(timer, NOW + timedelta(seconds=SHORT_BREAK_SECONDS - 1))
    assert result.timer == timer
    assert result.completed_pomodoro is None


def test_settle_resolves_short_break_elapsing_to_idle() -> None:
    timer = start_break(_ready_for_next(), NOW, completed_count=1)
    result = settle(timer, NOW + timedelta(seconds=SHORT_BREAK_SECONDS))
    assert result.timer.phase is TimerPhase.IDLE
    assert result.timer.task_id is None
    assert result.completed_pomodoro is None


def test_settle_resolves_long_break_elapsing_while_the_app_was_closed() -> None:
    timer = start_break(_ready_for_next(), NOW, completed_count=5)
    assert timer.break_kind is BreakKind.LONG
    much_later = NOW + timedelta(hours=3)

    result = settle(timer, much_later)

    assert result.timer.phase is TimerPhase.IDLE


def test_settle_does_not_resolve_a_paused_break() -> None:
    timer = start_break(_ready_for_next(), NOW, completed_count=1)
    paused = pause(timer, NOW + timedelta(seconds=10))
    result = settle(paused, NOW + timedelta(hours=1))
    assert result.timer == paused


# --- invalid action -> domain error (409 at the api layer) ----------------------


@pytest.mark.parametrize(
    "action",
    [
        lambda t: pause(t, NOW),
        lambda t: resume(t, NOW),
        lambda t: stop(t, NOW),
        log,
        discard,
        lambda t: start_break(t, NOW, completed_count=1),
        skip_break,
        lambda t: next_pomodoro(t, NOW),
    ],
)
def test_every_action_rejects_an_idle_timer_except_start(action) -> None:
    with pytest.raises(InvalidTimerActionError):
        action(idle_timer(USER))


# --- TimerRepository / PomodoroRepository Protocols -----------------------------


class FakeTimerRepository:
    """In-memory TimerRepository used to confirm the Protocol's shape."""

    def __init__(self) -> None:
        self._timers: dict[UserId, Timer] = {}

    def get(self, user_id: UserId) -> Timer | None:
        return self._timers.get(user_id)

    def save(self, user_id: UserId, timer: Timer) -> None:
        self._timers[user_id] = timer


class FakePomodoroRepository:
    """In-memory PomodoroRepository used to confirm the Protocol's shape."""

    def __init__(self) -> None:
        self._pomodoros: list[Pomodoro] = []
        self._next_id = 1

    def add(self, pomodoro: Pomodoro) -> Pomodoro:
        stored = Pomodoro(
            id=PomodoroId(self._next_id),
            user_id=pomodoro.user_id,
            task_id=pomodoro.task_id,
            started_at=pomodoro.started_at,
            ended_at=pomodoro.ended_at,
            duration_seconds=pomodoro.duration_seconds,
            status=pomodoro.status,
        )
        self._next_id += 1
        self._pomodoros.append(stored)
        return stored

    def count_completed_for_user(self, user_id: UserId) -> int:
        return sum(
            1
            for p in self._pomodoros
            if p.user_id == user_id and p.status is PomodoroStatus.COMPLETED
        )

    def exists_for_task(self, user_id: UserId, task_id: TaskId) -> bool:
        return any(p.user_id == user_id and p.task_id == task_id for p in self._pomodoros)


def test_fake_timer_repository_satisfies_the_protocol() -> None:
    repo: TimerRepository = FakeTimerRepository()
    assert isinstance(repo, TimerRepository)
    assert repo.get(USER) is None
    timer = start(idle_timer(USER), TASK, NOW)
    repo.save(USER, timer)
    assert repo.get(USER) == timer


def test_fake_pomodoro_repository_satisfies_the_protocol_and_scopes_counts_per_user() -> None:
    repo: PomodoroRepository = FakePomodoroRepository()
    assert isinstance(repo, PomodoroRepository)

    other_user = UserId(2)
    completed = settle(
        start(idle_timer(USER), TASK, NOW), NOW + timedelta(seconds=POMODORO_SECONDS)
    ).completed_pomodoro
    assert completed is not None
    repo.add(completed)

    assert repo.count_completed_for_user(USER) == 1
    assert repo.count_completed_for_user(other_user) == 0
    assert repo.exists_for_task(USER, TASK) is True
    assert repo.exists_for_task(USER, TaskId(999)) is False


def _ready_for_next(*, task_id: TaskId = TASK) -> Timer:
    return settle(
        start(idle_timer(USER), task_id, NOW), NOW + timedelta(seconds=POMODORO_SECONDS)
    ).timer
