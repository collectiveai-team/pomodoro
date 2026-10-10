"""Health-check router: proves the app is up and its dependency providers resolve."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pomodoro.api.v1.dependencies import get_clock
from pomodoro.api.v1.schemas.responses.health import HealthResponse
from pomodoro.core.clock import Clock
from pomodoro.database.session import DbSession, get_db_session

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health(
    clock: Clock = Depends(get_clock),
    _db_session: DbSession = Depends(get_db_session),
) -> HealthResponse:
    """Return 200 with the server's current time, proving the Clock/DB providers resolve."""
    return HealthResponse(status="ok", server_time=clock.now())
