"""HTTP tests for the protected Timer lifecycle through AskingToLog (T12)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from pomodoro.database.models.pomodoro import PomodoroTable
from sqlmodel import Session, select

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy import Engine
    from tests.conftest import FakeClock

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
TASKS_URL = "/api/v1/tasks"
TIMER_URL = "/api/v1/timer"


def _register(client: TestClient, *, email: str = "timer@example.com") -> None:
    client.post(
        REGISTER_URL,
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "time_zone": "America/Argentina/Buenos_Aires",
        },
    )


def _create_task(client: TestClient, text: str) -> str:
    response = client.post(TASKS_URL, json={"text": text})
    assert response.status_code == 201
    return response.json()["id"]


def test_start_persists_a_timer_for_the_callers_active_task(client: TestClient) -> None:
    _register(client)
    task_id = _create_task(client, "Write T12")

    response = client.post(
        f"{TIMER_URL}/start",
        json={"task_id": task_id, "expected_phase": "Idle"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "PomodoroRunning"
    assert body["task"] == {"id": task_id, "text": "Write T12"}
    assert body["remaining_seconds"] == 25 * 60
    assert client.get(TIMER_URL).json()["phase"] == "PomodoroRunning"


def test_timer_routes_require_an_authenticated_session(client: TestClient) -> None:
    assert client.get(TIMER_URL).status_code == 401
    assert (
        client.post(
            f"{TIMER_URL}/start",
            json={"task_id": "00000000-0000-0000-0000-000000000001", "expected_phase": "Idle"},
        ).status_code
        == 401
    )


def test_start_rejects_an_archived_or_another_users_task(client: TestClient) -> None:
    _register(client, email="owner@example.com")
    archived_task_id = _create_task(client, "Archived work")
    assert client.post(f"{TASKS_URL}/{archived_task_id}/archive").status_code == 200

    archived_response = client.post(
        f"{TIMER_URL}/start",
        json={"task_id": archived_task_id, "expected_phase": "Idle"},
    )
    assert archived_response.status_code == 404
    assert archived_response.json()["code"] == "task_not_found"

    other_task_id = _create_task(client, "Owner work")
    client.cookies.clear()
    _register(client, email="other@example.com")

    other_user_response = client.post(
        f"{TIMER_URL}/start",
        json={"task_id": other_task_id, "expected_phase": "Idle"},
    )
    assert other_user_response.status_code == 404
    assert other_user_response.json()["code"] == "task_not_found"


def test_pause_resume_and_stop_preserve_only_active_pomodoro_time(
    client: TestClient, fake_clock: FakeClock
) -> None:
    _register(client)
    task_id = _create_task(client, "Focused work")
    client.post(f"{TIMER_URL}/start", json={"task_id": task_id, "expected_phase": "Idle"})
    fake_clock.advance(timedelta(minutes=5))

    paused = client.post(f"{TIMER_URL}/pause", json={"expected_phase": "PomodoroRunning"})
    assert paused.status_code == 200
    assert paused.json()["accumulated_active_seconds"] == 300
    assert paused.json()["remaining_seconds"] == 1200

    fake_clock.advance(timedelta(minutes=10))
    resumed = client.post(f"{TIMER_URL}/resume", json={"expected_phase": "PomodoroPaused"})
    assert resumed.status_code == 200
    assert resumed.json()["remaining_seconds"] == 1200

    fake_clock.advance(timedelta(minutes=2))
    stopped = client.post(f"{TIMER_URL}/stop", json={"expected_phase": "PomodoroRunning"})
    assert stopped.status_code == 200
    assert stopped.json()["phase"] == "AskingToLog"
    assert stopped.json()["task"]["id"] == task_id
    assert stopped.json()["accumulated_active_seconds"] == 420
    assert stopped.json()["remaining_seconds"] is None


def test_stop_from_a_paused_pomodoro_keeps_its_task_and_active_time(
    client: TestClient, fake_clock: FakeClock
) -> None:
    _register(client)
    task_id = _create_task(client, "Paused work")
    client.post(f"{TIMER_URL}/start", json={"task_id": task_id, "expected_phase": "Idle"})
    fake_clock.advance(timedelta(seconds=90))
    client.post(f"{TIMER_URL}/pause", json={"expected_phase": "PomodoroRunning"})
    fake_clock.advance(timedelta(minutes=10))

    stopped = client.post(f"{TIMER_URL}/stop", json={"expected_phase": "PomodoroPaused"})

    assert stopped.status_code == 200
    assert stopped.json()["phase"] == "AskingToLog"
    assert stopped.json()["task"]["id"] == task_id
    assert stopped.json()["accumulated_active_seconds"] == 90


def test_elapsed_pomodoro_is_settled_once_with_its_exact_deadline(
    client: TestClient, fake_clock: FakeClock, db_engine: Engine
) -> None:
    _register(client)
    task_id = _create_task(client, "Finish chapter")
    client.post(f"{TIMER_URL}/start", json={"task_id": task_id, "expected_phase": "Idle"})
    fake_clock.advance(timedelta(minutes=26))

    settled = client.get(TIMER_URL)
    assert settled.status_code == 200
    assert settled.json()["phase"] == "ReadyForNext"
    assert settled.json()["accumulated_active_seconds"] == 1500
    assert settled.json()["running_since"] is None

    assert client.get(TIMER_URL).json()["phase"] == "ReadyForNext"
    with Session(db_engine) as session:
        pomodoros = session.exec(select(PomodoroTable)).all()

    assert len(pomodoros) == 1
    assert pomodoros[0].task_id == UUID(task_id)
    assert pomodoros[0].status == "completed"
    assert pomodoros[0].duration_seconds == 1500
    assert pomodoros[0].ended_at.isoformat() == "2026-01-01T00:25:00+00:00"


def test_stale_actions_return_the_current_timer_and_keep_its_task_binding(
    client: TestClient,
) -> None:
    _register(client)
    first_task_id = _create_task(client, "First task")
    second_task_id = _create_task(client, "Second task")
    client.post(f"{TIMER_URL}/start", json={"task_id": first_task_id, "expected_phase": "Idle"})
    assert (
        client.post(f"{TIMER_URL}/pause", json={"expected_phase": "PomodoroRunning"}).status_code
        == 200
    )

    stale_pause = client.post(f"{TIMER_URL}/pause", json={"expected_phase": "PomodoroRunning"})
    assert stale_pause.status_code == 409
    assert stale_pause.json()["phase"] == "PomodoroPaused"
    assert stale_pause.json()["task"]["id"] == first_task_id
    assert "server_now" in stale_pause.json()

    switched_task = client.post(
        f"{TIMER_URL}/start",
        json={"task_id": second_task_id, "expected_phase": "PomodoroPaused"},
    )
    assert switched_task.status_code == 409
    assert switched_task.json()["phase"] == "PomodoroPaused"
    assert switched_task.json()["task"]["id"] == first_task_id
