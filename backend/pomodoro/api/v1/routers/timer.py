"""Timer API: get, actions, and the day summary (T13).

Thin handlers: the Timer state machine itself stays in `core.timer` (T6, pure,
no I/O); persistence and the concurrency-safe settle-then-act transaction
delegate to `database.timer_repository.SqlTimerRepository.apply` (T13), scoped
to the authenticated User's `UserId` on every call. Every action settles the
Timer against the current instant first, inside the same atomic transaction,
so a stale cached phase can never let an action through that the clock has
already made invalid (T6/ADR-0003).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from pomodoro.api.v1 import dependencies as deps
from pomodoro.api.v1.schemas.requests.timer import StartTimerRequest
from pomodoro.api.v1.schemas.responses.timer import DaySummaryResponse, TimerResponse
from pomodoro.api.v1.session import require_json_content_type
from pomodoro.core import timer as core_timer
from pomodoro.core.entities import TaskId
from pomodoro.core.errors import TaskNotActiveError
from pomodoro.database.pomodoro_repository import SqlPomodoroRepository
from pomodoro.database.task_repository import SqlTaskRepository
from pomodoro.database.timer_repository import SqlTimerRepository
from pomodoro.database.user_repository import SqlUserRepository

if TYPE_CHECKING:
    from collections.abc import Callable

    from pomodoro.core.entities import AuthSession, Timer
    from pomodoro.core.timer import TimerUpdate

router = APIRouter(
    prefix="/timer", tags=["timer"], dependencies=[Depends(require_json_content_type)]
)


def to_response(timer: Timer, *, now: datetime) -> TimerResponse:
    """Build the outbound `TimerResponse`; also used by `entrypoints.app`'s 409 handler."""
    return TimerResponse(
        phase=timer.phase.value,
        task_id=timer.task_id,
        break_kind=timer.break_kind.value if timer.break_kind is not None else None,
        phase_started_at=timer.phase_started_at,
        phase_ended_at=timer.phase_ended_at,
        accumulated_active_seconds=timer.accumulated_active_seconds,
        remaining_seconds=core_timer.remaining_seconds(timer, now=now),
        server_now=now,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")


def _act(
    db_session: Session,
    auth_session: AuthSession,
    action: Callable[[Timer, datetime], Timer | TimerUpdate],
) -> TimerResponse:
    """Settle, then apply `action` to the settled Timer, in one atomic transaction (T13).

    Every route handler below is a one-line call into this: it owns `now`,
    the repository, and response-building, so an endpoint only ever supplies
    the one thing that differs between it and the rest - which `core.timer`
    action to run.

    `action` is one of `core.timer`'s action functions: most return a plain
    `Timer`, but `log` can itself produce a `PomodoroDraft` (an interrupted
    Pomodoro), so it returns a `TimerUpdate` instead - normalized here rather
    than duplicating this helper per return shape. `settle`'s own draft (a
    Pomodoro completed lazily, just now, by the clock) and `action`'s are never
    both set: `settle` only produces one when leaving PomodoroRunning, and no
    action valid from the resulting phase can itself produce one in the same
    tick, so `action`'s draft (when present) always wins.

    If `action` raises `TimerActionNotAllowedError` for the now-settled phase,
    nothing here is persisted - lazy settlement (ADR-0003) never needs an eager
    flush, so the exact same completion is simply resolved the next time the
    Timer is touched, and `entrypoints.app`'s handler reports the rejection
    with that already-settled Timer regardless.
    """
    now = datetime.now(UTC)

    def mutate(timer: Timer) -> TimerUpdate:
        settled = core_timer.settle(timer, now)
        raw = action(settled.timer, now)
        result = (
            raw if isinstance(raw, core_timer.TimerUpdate) else core_timer.TimerUpdate(timer=raw)
        )
        pomodoro = result.pomodoro if result.pomodoro is not None else settled.pomodoro
        return core_timer.TimerUpdate(timer=result.timer, pomodoro=pomodoro)

    update = SqlTimerRepository(db_session).apply(auth_session.user_id, mutate)
    return to_response(update.timer, now=now)


@router.get("")
def get_timer(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    """Return the authenticated User's Timer, settling it against `now` first."""
    return _act(db_session, auth_session, lambda t, _now: t)


@router.get("/day-summary")
def day_summary(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> DaySummaryResponse:
    """Completed-today (in the User's time zone, never UTC) and the Break countdown."""
    user = SqlUserRepository(db_session).get_by_id(auth_session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    completed = SqlPomodoroRepository(db_session).list_completed(auth_session.user_id)
    summary = core_timer.day_summary(completed, time_zone=user.time_zone, now=datetime.now(UTC))
    return DaySummaryResponse(
        completed_today=summary.completed_today,
        remaining_to_long_break=summary.remaining_to_long_break,
    )


@router.post("/start")
def start(
    payload: StartTimerRequest,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    """Start a Pomodoro against one of the User's own Active Tasks."""
    task = SqlTaskRepository(db_session).get(auth_session.user_id, TaskId(payload.task_id))
    if task is None:
        raise _not_found()
    if task.archived_at is not None:
        raise TaskNotActiveError(task.id)
    return _act(
        db_session, auth_session, lambda t, now: core_timer.start(t, task_id=task.id, now=now)
    )


@router.post("/pause")
def pause(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    return _act(db_session, auth_session, lambda t, now: core_timer.pause(t, now=now))


@router.post("/resume")
def resume(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    return _act(db_session, auth_session, lambda t, now: core_timer.resume(t, now=now))


@router.post("/stop")
def stop(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    return _act(db_session, auth_session, lambda t, now: core_timer.stop(t, now=now))


@router.post("/log")
def log(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    """Persist the interrupted Pomodoro frozen by `stop`; a double submit records it once."""
    return _act(db_session, auth_session, lambda t, _now: core_timer.log(t))


@router.post("/discard")
def discard(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    return _act(db_session, auth_session, lambda t, _now: core_timer.discard(t))


@router.post("/start-break")
def start_break(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    pomodoro_repo = SqlPomodoroRepository(db_session)

    def action(t: Timer, now: datetime) -> Timer:
        total_completed = len(pomodoro_repo.list_completed(auth_session.user_id))
        return core_timer.start_break(t, now=now, total_completed_pomodoros=total_completed)

    return _act(db_session, auth_session, action)


@router.post("/skip-break")
def skip_break(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    return _act(db_session, auth_session, lambda t, _now: core_timer.skip_break(t))


@router.post("/next-pomodoro")
def next_pomodoro(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TimerResponse:
    return _act(db_session, auth_session, lambda t, now: core_timer.next_pomodoro(t, now=now))
