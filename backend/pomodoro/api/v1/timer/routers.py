"""CES-17 · Protected Timer lifecycle endpoints and daily summary (T12-T13)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends

from pomodoro.api.v1.auth.dependencies import get_current_user
from pomodoro.api.v1.dependencies import get_clock
from pomodoro.api.v1.schemas.responses.error import ErrorResponse
from pomodoro.api.v1.timer.schemas.requests.start_timer import StartTimerRequest
from pomodoro.api.v1.timer.schemas.requests.timer_action import TimerActionRequest
from pomodoro.api.v1.timer.schemas.responses.timer import InProgressTaskResponse, TimerResponse
from pomodoro.api.v1.timer.use_cases import (
    TimerSnapshot,
    discard_timer,
    log_timer,
    next_pomodoro_timer,
    pause_timer,
    read_timer,
    resume_timer,
    skip_break_timer,
    start_break_timer,
    start_timer,
    stop_timer,
)
from pomodoro.core.clock import Clock
from pomodoro.core.tasks import TaskId, TaskRepository
from pomodoro.core.timer import PomodoroRepository, TimerRepository
from pomodoro.core.users import User
from pomodoro.database.repositories.pomodoro import get_pomodoro_repository
from pomodoro.database.repositories.task import get_task_repository
from pomodoro.database.repositories.timer import get_timer_repository

router = APIRouter(prefix="/timer", tags=["timer"])

_AUTH_ERROR_RESPONSE: dict[int | str, dict[str, Any]] = {401: {"model": ErrorResponse}}
_ACTION_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_AUTH_ERROR_RESPONSE,
    404: {"model": ErrorResponse},
    409: {"model": TimerResponse},
}


@dataclass
class TimerDependencies:
    """Bundled FastAPI-resolved collaborators shared by every Timer route."""

    user: User
    clock: Clock
    task_repository: TaskRepository
    timer_repository: TimerRepository
    pomodoro_repository: PomodoroRepository


def get_timer_dependencies(
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
    timer_repository: TimerRepository = Depends(get_timer_repository),
    pomodoro_repository: PomodoroRepository = Depends(get_pomodoro_repository),
) -> TimerDependencies:
    """Resolve the collaborators every Timer use case needs as one dependency."""
    return TimerDependencies(
        user=user,
        clock=clock,
        task_repository=task_repository,
        timer_repository=timer_repository,
        pomodoro_repository=pomodoro_repository,
    )


def timer_response(snapshot: TimerSnapshot) -> TimerResponse:
    """Translate the HTTP-neutral Timer view into its strict Pydantic response schema."""
    task = snapshot.task
    return TimerResponse(
        phase=snapshot.timer.phase,
        task=None if task is None else InProgressTaskResponse(id=task.id, text=task.text),
        break_kind=snapshot.timer.break_kind,
        phase_started_at=snapshot.timer.phase_started_at,
        accumulated_active_seconds=snapshot.timer.accumulated_active_seconds,
        running_since=snapshot.timer.running_since,
        server_now=snapshot.server_now,
        remaining_seconds=snapshot.remaining_seconds,
        pomodoros_completed_today=snapshot.daily_summary.pomodoros_completed_today,
        pomodoros_until_long_break=snapshot.daily_summary.pomodoros_until_long_break,
    )


def _dispatch_action(
    use_case: Callable[..., TimerSnapshot],
    payload: TimerActionRequest,
    deps: TimerDependencies,
) -> TimerResponse:
    """Call a phase-guarded Timer use case with the request's deps and wrap its result."""
    return timer_response(
        use_case(
            user_id=deps.user.id,
            expected_phase=payload.expected_phase,
            clock=deps.clock,
            task_repository=deps.task_repository,
            timer_repository=deps.timer_repository,
            pomodoro_repository=deps.pomodoro_repository,
            time_zone=deps.user.time_zone,
        )
    )


@router.get("", responses=_AUTH_ERROR_RESPONSE)
def get_timer(deps: TimerDependencies = Depends(get_timer_dependencies)) -> TimerResponse:
    """Return the caller's settled, durable Timer state."""
    return timer_response(
        read_timer(
            user_id=deps.user.id,
            clock=deps.clock,
            task_repository=deps.task_repository,
            timer_repository=deps.timer_repository,
            pomodoro_repository=deps.pomodoro_repository,
            time_zone=deps.user.time_zone,
        )
    )


@router.post("/start", responses=_ACTION_ERROR_RESPONSES)
def start(
    payload: StartTimerRequest,
    deps: TimerDependencies = Depends(get_timer_dependencies),
) -> TimerResponse:
    """Start a Pomodoro for a caller-owned Active Task."""
    return timer_response(
        start_timer(
            user_id=deps.user.id,
            task_id=TaskId(payload.task_id),
            expected_phase=payload.expected_phase,
            clock=deps.clock,
            task_repository=deps.task_repository,
            timer_repository=deps.timer_repository,
            pomodoro_repository=deps.pomodoro_repository,
            time_zone=deps.user.time_zone,
        )
    )


@router.post("/start-break", responses=_ACTION_ERROR_RESPONSES)
def start_break(
    payload: TimerActionRequest,
    deps: TimerDependencies = Depends(get_timer_dependencies),
) -> TimerResponse:
    """Start the short or long Break due after the caller's completed Pomodoros."""
    return _dispatch_action(start_break_timer, payload, deps)


@router.post("/skip-break", responses=_ACTION_ERROR_RESPONSES)
def skip_break(
    payload: TimerActionRequest,
    deps: TimerDependencies = Depends(get_timer_dependencies),
) -> TimerResponse:
    """Skip the caller's current Break without producing any Pomodoro time."""
    return _dispatch_action(skip_break_timer, payload, deps)


@router.post("/next-pomodoro", responses=_ACTION_ERROR_RESPONSES)
def next_pomodoro(
    payload: TimerActionRequest,
    deps: TimerDependencies = Depends(get_timer_dependencies),
) -> TimerResponse:
    """Begin another Pomodoro for the Task held after a completion."""
    return _dispatch_action(next_pomodoro_timer, payload, deps)


@router.post("/pause", responses=_ACTION_ERROR_RESPONSES)
def pause(
    payload: TimerActionRequest,
    deps: TimerDependencies = Depends(get_timer_dependencies),
) -> TimerResponse:
    """Pause the caller's running Pomodoro or Break after stale-tab protection."""
    return _dispatch_action(pause_timer, payload, deps)


@router.post("/resume", responses=_ACTION_ERROR_RESPONSES)
def resume(
    payload: TimerActionRequest,
    deps: TimerDependencies = Depends(get_timer_dependencies),
) -> TimerResponse:
    """Resume the caller's paused Pomodoro or Break after stale-tab protection."""
    return _dispatch_action(resume_timer, payload, deps)


@router.post("/stop", responses=_ACTION_ERROR_RESPONSES)
def stop(
    payload: TimerActionRequest,
    deps: TimerDependencies = Depends(get_timer_dependencies),
) -> TimerResponse:
    """Stop the caller's Pomodoro and move it to AskingToLog."""
    return _dispatch_action(stop_timer, payload, deps)


@router.post("/log", responses=_ACTION_ERROR_RESPONSES)
def log_interruption(
    payload: TimerActionRequest,
    deps: TimerDependencies = Depends(get_timer_dependencies),
) -> TimerResponse:
    """Log the caller's interrupted Pomodoro and reset its Timer to Idle."""
    return _dispatch_action(log_timer, payload, deps)


@router.post("/discard", responses=_ACTION_ERROR_RESPONSES)
def discard_interruption(
    payload: TimerActionRequest,
    deps: TimerDependencies = Depends(get_timer_dependencies),
) -> TimerResponse:
    """Discard the caller's interrupted Pomodoro and reset its Timer to Idle."""
    return _dispatch_action(discard_timer, payload, deps)
