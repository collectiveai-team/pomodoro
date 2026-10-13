"""API tests for starting a Pomodoro from ReadyForNext on any Active Task (ADR-0005)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from tests.conftest import create_task, register_user

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from tests.conftest import FakeClock

pytestmark = pytest.mark.unit

START_URL = "/api/v1/timer/start"


def _complete_pomodoro(client: TestClient, fake_clock: FakeClock, task_id: str) -> None:
    started = client.post(START_URL, json={"task_id": task_id, "expected_phase": "Idle"})
    assert started.status_code == 200
    fake_clock.advance(timedelta(minutes=25))
    assert client.get("/api/v1/timer").json()["phase"] == "ReadyForNext"


@pytest.mark.parametrize("same_task", [False, True])
def test_ready_for_next_starts_a_pomodoro_on_another_or_the_same_task(
    client: TestClient, fake_clock: FakeClock, same_task: bool
) -> None:
    register_user(client)
    first_id = create_task(client, "First")
    second_id = create_task(client, "Second")
    _complete_pomodoro(client, fake_clock, first_id)
    target = first_id if same_task else second_id

    response = client.post(START_URL, json={"task_id": target, "expected_phase": "ReadyForNext"})

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "PomodoroRunning"
    assert body["task"]["id"] == target
    assert body["break_kind"] is None
    assert body["remaining_seconds"] == 25 * 60


def test_skipping_the_break_does_not_change_the_completed_count(
    client: TestClient, fake_clock: FakeClock
) -> None:
    register_user(client)
    first_id = create_task(client, "First")
    second_id = create_task(client, "Second")
    _complete_pomodoro(client, fake_clock, first_id)
    before = client.get("/api/v1/timer").json()

    started = client.post(
        START_URL, json={"task_id": second_id, "expected_phase": "ReadyForNext"}
    ).json()

    assert started["pomodoros_completed_today"] == before["pomodoros_completed_today"] == 1
    assert started["pomodoros_until_long_break"] == 4


def test_stale_expected_phase_returns_409_with_the_current_snapshot(
    client: TestClient, fake_clock: FakeClock
) -> None:
    register_user(client)
    first_id = create_task(client, "First")
    second_id = create_task(client, "Second")
    _complete_pomodoro(client, fake_clock, first_id)

    stale = client.post(START_URL, json={"task_id": second_id, "expected_phase": "Idle"})

    assert stale.status_code == 409
    assert stale.json()["phase"] == "ReadyForNext"
    assert stale.json()["task"]["id"] == first_id


def test_ready_for_next_rejects_an_archived_or_another_users_task(
    client: TestClient, fake_clock: FakeClock
) -> None:
    register_user(client, email="owner@example.com")
    first_id = create_task(client, "First")
    archived_id = create_task(client, "Archived")
    assert client.post(f"/api/v1/tasks/{archived_id}/archive").status_code == 200
    _complete_pomodoro(client, fake_clock, first_id)
    client.cookies.clear()
    register_user(client, email="other@example.com")
    foreign_task_id = create_task(client, "Foreign")
    client.cookies.clear()
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct-horse-battery-staple"},
    )

    for task_id in (archived_id, foreign_task_id):
        response = client.post(
            START_URL, json={"task_id": task_id, "expected_phase": "ReadyForNext"}
        )
        assert response.status_code == 404
        assert response.json()["code"] == "task_not_found"
    assert client.get("/api/v1/timer").json()["phase"] == "ReadyForNext"
