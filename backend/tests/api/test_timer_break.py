"""HTTP tests for Break lifecycle and Timer daily summary (T13)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from pomodoro.database.models.pomodoro import PomodoroTable
from sqlmodel import Session, select

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy import Engine
    from tests.conftest import FakeClock

pytestmark = pytest.mark.unit


def _register(client: TestClient, *, email: str, time_zone: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "time_zone": time_zone,
        },
    )
    assert response.status_code == 201


def _create_task(client: TestClient, text: str) -> str:
    response = client.post("/api/v1/tasks", json={"text": text})
    assert response.status_code == 201
    return response.json()["id"]


def _complete_pomodoro(client: TestClient, fake_clock: FakeClock, task_id: str) -> None:
    response = client.post(
        "/api/v1/timer/start", json={"task_id": task_id, "expected_phase": "Idle"}
    )
    assert response.status_code == 200
    fake_clock.advance(timedelta(minutes=25))
    assert client.get("/api/v1/timer").json()["phase"] == "ReadyForNext"


def _continue_completed_pomodoro(client: TestClient, fake_clock: FakeClock) -> None:
    response = client.post("/api/v1/timer/next-pomodoro", json={"expected_phase": "ReadyForNext"})
    assert response.status_code == 200
    fake_clock.advance(timedelta(minutes=25))
    assert client.get("/api/v1/timer").json()["phase"] == "ReadyForNext"


def _start_short_break(client: TestClient, fake_clock: FakeClock) -> None:
    task_id = _create_task(client, "Break task")
    _complete_pomodoro(client, fake_clock, task_id)
    response = client.post("/api/v1/timer/start-break", json={"expected_phase": "ReadyForNext"})
    assert response.status_code == 200
    assert response.json()["break_kind"] == "short"


def _pomodoros(db_engine: Engine) -> list[PomodoroTable]:
    with Session(db_engine) as session:
        return list(session.exec(select(PomodoroTable)))


def test_completed_pomodoro_offers_a_short_break_and_daily_summary(
    client: TestClient, fake_clock: FakeClock
) -> None:
    """The first completed Pomodoro yields the five-minute Break and today's counts."""
    _register(client, email="break@example.com", time_zone="America/Argentina/Buenos_Aires")
    task_id = _create_task(client, "Rest after focus")
    _complete_pomodoro(client, fake_clock, task_id)
    started_break = client.post(
        "/api/v1/timer/start-break", json={"expected_phase": "ReadyForNext"}
    )

    assert started_break.status_code == 200
    assert started_break.json()["phase"] == "BreakRunning"
    assert started_break.json()["break_kind"] == "short"
    assert started_break.json()["remaining_seconds"] == 5 * 60
    assert started_break.json()["pomodoros_completed_today"] == 1
    assert started_break.json()["pomodoros_until_long_break"] == 4


def test_fifth_completed_pomodoro_offers_a_long_break(
    client: TestClient, fake_clock: FakeClock
) -> None:
    """The long Break is due exactly after a User's fifth completed Pomodoro."""
    _register(client, email="long-break@example.com", time_zone="America/Argentina/Buenos_Aires")
    task_id = _create_task(client, "Five focused intervals")
    _complete_pomodoro(client, fake_clock, task_id)

    for _ in range(2, 6):
        _continue_completed_pomodoro(client, fake_clock)

    started_break = client.post(
        "/api/v1/timer/start-break", json={"expected_phase": "ReadyForNext"}
    )

    assert started_break.status_code == 200
    assert started_break.json()["phase"] == "BreakRunning"
    assert started_break.json()["break_kind"] == "long"
    assert started_break.json()["remaining_seconds"] == 10 * 60
    assert started_break.json()["pomodoros_completed_today"] == 5
    assert started_break.json()["pomodoros_until_long_break"] == 0


def test_break_pause_resume_skip_and_stale_actions_return_current_timer(
    client: TestClient, fake_clock: FakeClock
) -> None:
    """Break controls share phase guards with Pomodoros and retain no Break record."""
    _register(client, email="skip@example.com", time_zone="America/Argentina/Buenos_Aires")
    _start_short_break(client, fake_clock)
    fake_clock.advance(timedelta(minutes=2))

    paused = client.post("/api/v1/timer/pause", json={"expected_phase": "BreakRunning"})
    assert paused.status_code == 200
    assert paused.json()["phase"] == "BreakPaused"
    assert paused.json()["accumulated_active_seconds"] == 120

    stale_pause = client.post("/api/v1/timer/pause", json={"expected_phase": "BreakRunning"})
    assert stale_pause.status_code == 409
    assert stale_pause.json()["phase"] == "BreakPaused"

    fake_clock.advance(timedelta(minutes=5))
    resumed = client.post("/api/v1/timer/resume", json={"expected_phase": "BreakPaused"})
    assert resumed.status_code == 200
    assert resumed.json()["phase"] == "BreakRunning"
    assert resumed.json()["remaining_seconds"] == 3 * 60

    stale_resume = client.post("/api/v1/timer/resume", json={"expected_phase": "BreakPaused"})
    assert stale_resume.status_code == 409
    assert stale_resume.json()["phase"] == "BreakRunning"

    skipped = client.post("/api/v1/timer/skip-break", json={"expected_phase": "BreakRunning"})
    assert skipped.status_code == 200
    assert skipped.json()["phase"] == "Idle"
    assert skipped.json()["task"] is None
    assert skipped.json()["pomodoros_completed_today"] == 1

    for endpoint in ("start-break", "skip-break", "next-pomodoro"):
        stale = client.post(f"/api/v1/timer/{endpoint}", json={"expected_phase": "ReadyForNext"})
        assert stale.status_code == 409
        assert stale.json()["phase"] == "Idle"


def test_naturally_elapsed_break_returns_idle_without_dedicated_task_time(
    client: TestClient, fake_clock: FakeClock, db_engine: Engine
) -> None:
    """Only the completed Pomodoro is recorded when the following Break runs out."""
    _register(client, email="natural@example.com", time_zone="America/Argentina/Buenos_Aires")
    _start_short_break(client, fake_clock)
    fake_clock.advance(timedelta(minutes=5))

    settled = client.get("/api/v1/timer")

    assert settled.status_code == 200
    assert settled.json()["phase"] == "Idle"
    assert settled.json()["task"] is None
    assert settled.json()["pomodoros_completed_today"] == 1
    pomodoros = _pomodoros(db_engine)
    assert len(pomodoros) == 1
    assert pomodoros[0].status == "completed"
    assert pomodoros[0].duration_seconds == 25 * 60


def test_daily_summary_counts_a_pomodoro_ending_at_local_midnight(
    client: TestClient, fake_clock: FakeClock
) -> None:
    """A completion is counted on its User-local ending day, including exact midnight."""
    _register(client, email="midnight@example.com", time_zone="Pacific/Auckland")
    task_id = _create_task(client, "Cross a local date")
    fake_clock.advance(timedelta(hours=10, minutes=35))

    _complete_pomodoro(client, fake_clock, task_id)
    summary = client.get("/api/v1/timer")

    assert summary.status_code == 200
    assert summary.json()["server_now"] == "2026-01-01T11:00:00Z"
    assert summary.json()["pomodoros_completed_today"] == 1
    assert summary.json()["pomodoros_until_long_break"] == 4
