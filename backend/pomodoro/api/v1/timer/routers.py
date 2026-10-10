"""CES-17 · Protected Timer lifecycle endpoints through AskingToLog (T12)."""

from __future__ import annotations

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
    pause_timer,
    read_timer,
    resume_timer,
    start_timer,
    stop_timer,
)
from pomodoro.core.clock import Clock
from pomodoro.core.tasks import TaskId, TaskRepository
from pomodoro.core.timer import TimerRepository
from pomodoro.core.users import User
from pomodoro.database.repositories.task import get_task_repository
from pomodoro.database.repositories.timer import get_timer_repository

router = APIRouter(prefix="/timer", tags=["timer"])

_AUTH_ERROR_RESPONSE: dict[int | str, dict[str, Any]] = {401: {"model": ErrorResponse}}
_ACTION_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_AUTH_ERROR_RESPONSE,
    404: {"model": ErrorResponse},
    409: {"model": TimerResponse},
}


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
    )


@router.get("", responses=_AUTH_ERROR_RESPONSE)
def get_timer(
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
    timer_repository: TimerRepository = Depends(get_timer_repository),
) -> TimerResponse:
    """Return the caller's settled, durable Timer state."""
    return timer_response(
        read_timer(
            user_id=user.id,
            clock=clock,
            task_repository=task_repository,
            timer_repository=timer_repository,
        )
    )


@router.post("/start", responses=_ACTION_ERROR_RESPONSES)
def start(
    payload: StartTimerRequest,
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
    timer_repository: TimerRepository = Depends(get_timer_repository),
) -> TimerResponse:
    """Start a Pomodoro for a caller-owned Active Task."""
    return timer_response(
        start_timer(
            user_id=user.id,
            task_id=TaskId(payload.task_id),
            expected_phase=payload.expected_phase,
            clock=clock,
            task_repository=task_repository,
            timer_repository=timer_repository,
        )
    )


@router.post("/pause", responses=_ACTION_ERROR_RESPONSES)
def pause(
    payload: TimerActionRequest,
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
    timer_repository: TimerRepository = Depends(get_timer_repository),
) -> TimerResponse:
    """Pause the caller's running Pomodoro after stale-tab protection."""
    return timer_response(
        pause_timer(
            user_id=user.id,
            expected_phase=payload.expected_phase,
            clock=clock,
            task_repository=task_repository,
            timer_repository=timer_repository,
        )
    )


@router.post("/resume", responses=_ACTION_ERROR_RESPONSES)
def resume(
    payload: TimerActionRequest,
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
    timer_repository: TimerRepository = Depends(get_timer_repository),
) -> TimerResponse:
    """Resume the caller's paused Pomodoro after stale-tab protection."""
    return timer_response(
        resume_timer(
            user_id=user.id,
            expected_phase=payload.expected_phase,
            clock=clock,
            task_repository=task_repository,
            timer_repository=timer_repository,
        )
    )


@router.post("/stop", responses=_ACTION_ERROR_RESPONSES)
def stop(
    payload: TimerActionRequest,
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
    timer_repository: TimerRepository = Depends(get_timer_repository),
) -> TimerResponse:
    """Stop the caller's Pomodoro and move it to AskingToLog."""
    return timer_response(
        stop_timer(
            user_id=user.id,
            expected_phase=payload.expected_phase,
            clock=clock,
            task_repository=task_repository,
            timer_repository=timer_repository,
        )
    )


@router.post("/log", responses=_ACTION_ERROR_RESPONSES)
def log_interruption(
    payload: TimerActionRequest,
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
    timer_repository: TimerRepository = Depends(get_timer_repository),
) -> TimerResponse:
    """Log the caller's interrupted Pomodoro and reset its Timer to Idle."""
    return timer_response(
        log_timer(
            user_id=user.id,
            expected_phase=payload.expected_phase,
            clock=clock,
            task_repository=task_repository,
            timer_repository=timer_repository,
        )
    )


@router.post("/discard", responses=_ACTION_ERROR_RESPONSES)
def discard_interruption(
    payload: TimerActionRequest,
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
    timer_repository: TimerRepository = Depends(get_timer_repository),
) -> TimerResponse:
    """Discard the caller's interrupted Pomodoro and reset its Timer to Idle."""
    return timer_response(
        discard_timer(
            user_id=user.id,
            expected_phase=payload.expected_phase,
            clock=clock,
            task_repository=task_repository,
            timer_repository=timer_repository,
        )
    )
