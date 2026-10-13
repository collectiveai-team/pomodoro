"""Guard: a Task referenced by the caller's Timer in a non-Idle phase (T14, User Story 31)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from tests.conftest import create_task, register_user

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from tests.conftest import FakeClock

pytestmark = pytest.mark.unit

TASKS_URL = "/api/v1/tasks"
TIMER_URL = "/api/v1/timer"


def _task_with_running_pomodoro(client: TestClient, text: str) -> str:
    """Create a Task and immediately start a Pomodoro for it, returning its id."""
    task_id = create_task(client, text)
    started = client.post(f"{TIMER_URL}/start", json={"task_id": task_id, "expected_phase": "Idle"})
    assert started.status_code == 200
    return task_id


def _task_returned_to_idle_after_an_interrupted_pomodoro(client: TestClient, text: str) -> str:
    """Create a Task, run then discard an interrupted Pomodoro on it, leaving the Timer Idle."""
    task_id = _task_with_running_pomodoro(client, text)
    stop_response = client.post(f"{TIMER_URL}/stop", json={"expected_phase": "PomodoroRunning"})
    assert stop_response.status_code == 200
    discard_response = client.post(f"{TIMER_URL}/discard", json={"expected_phase": "AskingToLog"})
    assert discard_response.status_code == 200
    assert discard_response.json()["phase"] == "Idle"
    return task_id


def _task_with_running_break(client: TestClient, fake_clock: FakeClock, text: str) -> str:
    """Create a Task, complete a Pomodoro on it, and start the resulting Break."""
    task_id = _task_with_running_pomodoro(client, text)
    fake_clock.advance(timedelta(minutes=25))
    assert client.get(TIMER_URL).json()["phase"] == "ReadyForNext"
    response = client.post(f"{TIMER_URL}/start-break", json={"expected_phase": "ReadyForNext"})
    assert response.status_code == 200
    assert response.json()["phase"] == "BreakRunning"
    return task_id


def test_archive_is_blocked_while_a_pomodoro_is_running_on_that_task(client: TestClient) -> None:
    register_user(client)
    task_id = _task_with_running_pomodoro(client, "Write report")

    response = client.post(f"{TASKS_URL}/{task_id}/archive")

    assert response.status_code == 409
    assert response.json()["code"] == "task_in_use_by_timer"


def test_delete_is_blocked_while_a_pomodoro_is_running_on_that_task(client: TestClient) -> None:
    register_user(client)
    task_id = _task_with_running_pomodoro(client, "Write report")

    response = client.delete(f"{TASKS_URL}/{task_id}")

    assert response.status_code == 409
    assert response.json()["code"] == "task_in_use_by_timer"


def test_archive_is_blocked_while_a_break_is_running_on_that_task(
    client: TestClient, fake_clock: FakeClock
) -> None:
    register_user(client)
    task_id = _task_with_running_break(client, fake_clock, "Rest after focus")

    response = client.post(f"{TASKS_URL}/{task_id}/archive")

    assert response.status_code == 409
    assert response.json()["code"] == "task_in_use_by_timer"


def test_delete_is_blocked_while_a_break_is_running_on_that_task(
    client: TestClient, fake_clock: FakeClock
) -> None:
    register_user(client)
    task_id = _task_with_running_break(client, fake_clock, "Rest after focus")

    response = client.delete(f"{TASKS_URL}/{task_id}")

    assert response.status_code == 409
    assert response.json()["code"] == "task_in_use_by_timer"


def test_archive_is_allowed_again_once_the_timer_returns_to_idle(client: TestClient) -> None:
    register_user(client)
    task_id = _task_returned_to_idle_after_an_interrupted_pomodoro(client, "Write report")

    response = client.post(f"{TASKS_URL}/{task_id}/archive")

    assert response.status_code == 200


def test_delete_is_allowed_again_once_the_timer_returns_to_idle(client: TestClient) -> None:
    register_user(client)
    task_id = _task_returned_to_idle_after_an_interrupted_pomodoro(client, "Write report")

    response = client.delete(f"{TASKS_URL}/{task_id}")

    assert response.status_code == 204


def test_archiving_a_different_task_is_unaffected_by_an_in_progress_timer(
    client: TestClient,
) -> None:
    register_user(client)
    other_task_id = create_task(client, "Untouched")
    _task_with_running_pomodoro(client, "In progress")

    response = client.post(f"{TASKS_URL}/{other_task_id}/archive")

    assert response.status_code == 200
