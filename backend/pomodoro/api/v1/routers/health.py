"""GET /health — a thin liveness check, no business logic."""

from __future__ import annotations

from fastapi import APIRouter

from pomodoro.api.v1.schemas.responses.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> HealthResponse:
    return HealthResponse()
