"""Health/readiness route. The app factory overrides `get_clock` with a real Clock."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pomodoro.core.clock import Clock

router = APIRouter()


class HealthResponse(BaseModel):
    """Public shape of the health route's response."""

    status: str
    time: datetime


def get_clock() -> Clock:
    """Stand in for the Clock dependency until the app factory overrides it."""
    raise NotImplementedError("Clock dependency must be wired by the app factory")


@router.get("/health")
def health(clock: Annotated[Clock, Depends(get_clock)]) -> HealthResponse:
    """Report readiness and the server's current time."""
    return HealthResponse(status="ok", time=clock.now())
