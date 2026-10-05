"""Timer API: resolved-Timer read, every action, and the day's Pomodoro summary.

Per the house convention (api/<area> owns router + schemas + use case), the
orchestration lives here; `pomodoro.core.timer` supplies the framework-free
state machine, lazy `settle()`, and break cadence, and `pomodoro.api.session`
supplies the authenticated `User` every route below requires. `TaskRepository`
and `PomodoroRepository` are reused from `pomodoro.api.tasks` rather than
wired a second time.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from pomodoro.api.session import get_clock, require_session
from pomodoro.api.tasks import (
    NOT_FOUND_ERROR,
    get_pomodoro_repository,
    get_task_repository,
    get_timer_repository,
)
from pomodoro.core.clock import Clock
from pomodoro.core.entities import Task, TaskId, User
from pomodoro.core.errors import InvalidTimerActionError, TaskNotActiveError
from pomodoro.core.repositories import PomodoroRepository, TaskRepository, TimerRepository
from pomodoro.core.timer import (
    POMODORO_SECONDS,
    Timer,
    TimerPhase,
    active_seconds,
    break_duration_seconds,
    discard,
    local_day_bounds_utc,
    log,
    next_pomodoro,
    pause,
    pomodoros_until_long_break,
    resume,
    settle_and_persist,
    skip_break,
    start_break,
    start_on_task,
    stop,
)

if TYPE_CHECKING:
    from collections.abc import Callable

router = APIRouter(prefix="/api/timer", tags=["timer"])


UserDep = Annotated[User, Depends(require_session)]
ClockDep = Annotated[Clock, Depends(get_clock)]
TimerRepoDep = Annotated[TimerRepository, Depends(get_timer_repository)]
TaskRepoDep = Annotated[TaskRepository, Depends(get_task_repository)]
PomodoroRepoDep = Annotated[PomodoroRepository, Depends(get_pomodoro_repository)]


class StartTimerRequest(BaseModel):
    """Request body for `POST /api/timer/start`."""

    task_id: int


class InProgressTaskPublic(BaseModel):
    """The minimal Task shape surfaced alongside the Timer."""

    id: int
    text: str


class TimerPublic(BaseModel):
    """The settled Timer as exposed over HTTP, plus client clock-offset correction data."""

    phase: str
    task: InProgressTaskPublic | None
    break_kind: str | None
    remaining_seconds: int | None
    server_now: datetime

    @classmethod
    def build(cls, timer: Timer, now: datetime, task: Task | None) -> TimerPublic:
        return cls(
            phase=timer.phase.value,
            task=InProgressTaskPublic(id=task.id, text=task.text) if task is not None else None,
            break_kind=timer.break_kind.value if timer.break_kind is not None else None,
            remaining_seconds=_remaining_seconds(timer, now),
            server_now=now,
        )


class DaySummaryPublic(BaseModel):
    """Today's completed-Pomodoro count and the distance to the next long Break."""

    completed_today: int
    until_long_break: int


def _remaining_seconds(timer: Timer, now: datetime) -> int | None:
    if timer.phase in (TimerPhase.POMODORO_RUNNING, TimerPhase.POMODORO_PAUSED):
        return max(POMODORO_SECONDS - active_seconds(timer, now), 0)
    if timer.phase in (TimerPhase.BREAK_RUNNING, TimerPhase.BREAK_PAUSED):
        break_kind = timer.break_kind
        if break_kind is None:
            raise AssertionError
        return max(break_duration_seconds(break_kind) - active_seconds(timer, now), 0)
    return None


def _lookup_task(task_repo: TaskRepository, user: User, task_id: TaskId | None) -> Task | None:
    if task_id is None:
        return None
    return task_repo.get(user.id, task_id)


def _conflict(timer: Timer, now: datetime, task: Task | None) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail=TimerPublic.build(timer, now, task).model_dump(mode="json"),
    )


def _apply_action(
    action: Callable[[Timer, datetime], Timer],
    user: User,
    timer_repo: TimerRepository,
    pomodoro_repo: PomodoroRepository,
    task_repo: TaskRepository,
    clock: Clock,
) -> TimerPublic:
    now = clock.now()
    timer = settle_and_persist(timer_repo, pomodoro_repo, user.id, now)
    try:
        updated = action(timer, now)
    except InvalidTimerActionError as error:
        raise _conflict(timer, now, _lookup_task(task_repo, user, timer.task_id)) from error
    timer_repo.save(user.id, updated)
    task = _lookup_task(task_repo, user, updated.task_id)
    return TimerPublic.build(updated, now, task)


@router.get("")
def get_timer(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """Return the settled Timer, the in-progress Task, remaining time and the server's `now`."""
    now = clock.now()
    timer = settle_and_persist(timer_repo, pomodoro_repo, user.id, now)
    task = _lookup_task(task_repo, user, timer.task_id)
    return TimerPublic.build(timer, now, task)


@router.get("/summary")
def get_day_summary(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    clock: ClockDep,
) -> DaySummaryPublic:
    """Return today's completed-Pomodoro count and how many more until the next long Break."""
    now = clock.now()
    settle_and_persist(timer_repo, pomodoro_repo, user.id, now)
    start_utc, end_utc = local_day_bounds_utc(now, user.time_zone)
    completed_today = pomodoro_repo.count_completed_between(user.id, start_utc, end_utc)
    total_completed = pomodoro_repo.count_completed_for_user(user.id)
    return DaySummaryPublic(
        completed_today=completed_today,
        until_long_break=pomodoros_until_long_break(total_completed),
    )


@router.post("/start")
def start_timer(
    body: StartTimerRequest,
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """Start a Pomodoro on one of the caller's own Active Tasks."""
    now = clock.now()
    timer = settle_and_persist(timer_repo, pomodoro_repo, user.id, now)
    task = task_repo.get(user.id, TaskId(body.task_id))
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_ERROR)
    try:
        updated = start_on_task(timer, task, now)
    except TaskNotActiveError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except InvalidTimerActionError as error:
        raise _conflict(timer, now, _lookup_task(task_repo, user, timer.task_id)) from error
    timer_repo.save(user.id, updated)
    return TimerPublic.build(updated, now, task)


@router.post("/pause")
def pause_timer(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """PomodoroRunning/BreakRunning -> paused."""
    return _apply_action(pause, user, timer_repo, pomodoro_repo, task_repo, clock)


@router.post("/resume")
def resume_timer(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """PomodoroPaused/BreakPaused -> running."""
    return _apply_action(resume, user, timer_repo, pomodoro_repo, task_repo, clock)


@router.post("/stop")
def stop_timer(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """PomodoroRunning/PomodoroPaused + stop -> AskingToLog."""
    return _apply_action(stop, user, timer_repo, pomodoro_repo, task_repo, clock)


@router.post("/log")
def log_timer(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """AskingToLog + log -> Idle, persisting the interrupted Pomodoro's real time."""
    now = clock.now()
    timer = settle_and_persist(timer_repo, pomodoro_repo, user.id, now)
    try:
        result = log(timer)
    except InvalidTimerActionError as error:
        raise _conflict(timer, now, _lookup_task(task_repo, user, timer.task_id)) from error
    if result.pomodoro is not None:
        pomodoro_repo.add(result.pomodoro)
    timer_repo.save(user.id, result.timer)
    return TimerPublic.build(result.timer, now, None)


@router.post("/discard")
def discard_timer(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """AskingToLog + discard -> Idle, persisting nothing."""
    return _apply_action(
        lambda timer, _now: discard(timer), user, timer_repo, pomodoro_repo, task_repo, clock
    )


@router.post("/start-break")
def start_break_timer(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """ReadyForNext + start-break -> BreakRunning, short or long by cadence."""

    def _start_break(timer: Timer, now: datetime) -> Timer:
        completed_count = pomodoro_repo.count_completed_for_user(user.id)
        return start_break(timer, now, completed_count)

    return _apply_action(_start_break, user, timer_repo, pomodoro_repo, task_repo, clock)


@router.post("/skip-break")
def skip_break_timer(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """ReadyForNext/BreakRunning/BreakPaused + skip-break -> Idle, no Alarm."""
    return _apply_action(
        lambda timer, _now: skip_break(timer), user, timer_repo, pomodoro_repo, task_repo, clock
    )


@router.post("/next-pomodoro")
def next_pomodoro_timer(
    user: UserDep,
    timer_repo: TimerRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    task_repo: TaskRepoDep,
    clock: ClockDep,
) -> TimerPublic:
    """ReadyForNext + next-pomodoro -> PomodoroRunning on the same Task."""
    return _apply_action(next_pomodoro, user, timer_repo, pomodoro_repo, task_repo, clock)
