"""Unit tests for Task lifecycle endpoints (CES-4, CES-17; User Stories 15, 20, 22-30)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from pomodoro.database.models.pomodoro import PomodoroTable
from sqlmodel import Session

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy import Engine
    from tests.conftest import FakeClock

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
ME_URL = "/api/v1/auth/me"
TASKS_URL = "/api/v1/tasks"


def _register(client: TestClient, *, email: str = "owner@example.com") -> None:
    client.post(
        REGISTER_URL,
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "time_zone": "America/Argentina/Buenos_Aires",
        },
    )


def _create(client: TestClient, text: str) -> dict:  # ast-grep-ignore: no-dict-return-annotation
    return client.post(TASKS_URL, json={"text": text}).json()


def _record_pomodoro(db_engine: Engine, *, user_id: UUID, task_id: UUID) -> None:
    with Session(db_engine) as session:
        session.add(
            PomodoroTable(
                user_id=user_id,
                task_id=task_id,
                started_at=datetime(2026, 1, 1, tzinfo=UTC),
                ended_at=datetime(2026, 1, 1, 0, 25, tzinfo=UTC),
                duration_seconds=1500,
                status="completed",
            )
        )
        session.commit()


def test_newly_created_task_is_deletable(client: TestClient) -> None:
    _register(client)

    task = _create(client, "Write report")

    assert task["deletable"] is True


def test_archive_freezes_position_and_sets_archived_at(client: TestClient) -> None:
    _register(client)
    task = _create(client, "Write report")

    response = client.post(f"{TASKS_URL}/{task['id']}/archive")

    assert response.status_code == 200
    body = response.json()
    assert body["position"] == task["position"]
    assert body["archived_at"] is not None

    listing = client.get(TASKS_URL).json()
    assert listing["tasks"] == []
    assert listing["active_count"] == 0
    assert listing["archived_count"] == 1


def test_unarchive_clears_archived_at_and_appends_at_the_end(client: TestClient) -> None:
    _register(client)
    first = _create(client, "First")
    second = _create(client, "Second")
    client.post(f"{TASKS_URL}/{second['id']}/archive")

    response = client.post(f"{TASKS_URL}/{second['id']}/unarchive")

    assert response.status_code == 200
    body = response.json()
    assert body["archived_at"] is None
    assert body["position"] > first["position"]

    active_texts = [task["text"] for task in client.get(TASKS_URL).json()["tasks"]]
    assert active_texts == ["First", "Second"]


def test_unarchive_rejects_text_collision_with_an_active_task(client: TestClient) -> None:
    _register(client)
    archived = _create(client, "Write report")
    client.post(f"{TASKS_URL}/{archived['id']}/archive")
    _create(client, "Write report")

    response = client.post(f"{TASKS_URL}/{archived['id']}/unarchive")

    assert response.status_code == 422
    assert response.json()["code"] == "duplicate_task_text"


def test_create_task_with_text_matching_an_archived_task_succeeds(client: TestClient) -> None:
    _register(client)
    task = _create(client, "Write report")
    client.post(f"{TASKS_URL}/{task['id']}/archive")

    response = client.post(TASKS_URL, json={"text": "Write report"})

    assert response.status_code == 201


def test_reorder_rewrites_active_task_positions_as_0_to_n_minus_1(client: TestClient) -> None:
    _register(client)
    first = _create(client, "A")
    second = _create(client, "B")
    third = _create(client, "C")

    response = client.put(
        f"{TASKS_URL}/reorder",
        json={"task_ids": [first["id"], second["id"], third["id"]]},
    )

    assert response.status_code == 200
    positions = {task["text"]: task["position"] for task in response.json()}
    assert positions == {"A": 0, "B": 1, "C": 2}

    active_texts = [task["text"] for task in client.get(TASKS_URL).json()["tasks"]]
    assert active_texts == ["A", "B", "C"]


def test_reorder_rejects_a_list_that_does_not_match_the_active_task_ids(
    client: TestClient,
) -> None:
    _register(client)
    first = _create(client, "A")
    _create(client, "B")

    response = client.put(f"{TASKS_URL}/reorder", json={"task_ids": [first["id"]]})

    assert response.status_code == 422
    assert response.json()["code"] == "task_reorder_mismatch"


def test_get_archived_tasks_lists_most_recently_archived_first(
    client: TestClient, fake_clock: FakeClock
) -> None:
    _register(client)
    first = _create(client, "First")
    second = _create(client, "Second")

    client.post(f"{TASKS_URL}/{first['id']}/archive")
    fake_clock.advance(timedelta(minutes=1))
    client.post(f"{TASKS_URL}/{second['id']}/archive")

    response = client.get(f"{TASKS_URL}/archived")

    assert response.status_code == 200
    body = response.json()
    assert [task["text"] for task in body["tasks"]] == ["Second", "First"]
    assert body["active_count"] == 0
    assert body["archived_count"] == 2


def test_delete_task_succeeds_when_no_pomodoros_were_recorded(client: TestClient) -> None:
    _register(client)
    task = _create(client, "Write report")

    response = client.delete(f"{TASKS_URL}/{task['id']}")

    assert response.status_code == 204
    assert client.get(TASKS_URL).json()["tasks"] == []


def test_delete_task_is_blocked_when_a_pomodoro_was_recorded(
    client: TestClient, db_engine: Engine
) -> None:
    _register(client)
    user_id = UUID(client.get(ME_URL).json()["id"])
    task = _create(client, "Write report")
    _record_pomodoro(db_engine, user_id=user_id, task_id=UUID(task["id"]))

    response = client.delete(f"{TASKS_URL}/{task['id']}")

    assert response.status_code == 409
    assert response.json()["code"] == "task_has_recorded_pomodoros"


def test_task_with_a_recorded_pomodoro_is_not_deletable_in_listings(
    client: TestClient, db_engine: Engine
) -> None:
    _register(client)
    user_id = UUID(client.get(ME_URL).json()["id"])
    task = _create(client, "Write report")
    _record_pomodoro(db_engine, user_id=user_id, task_id=UUID(task["id"]))

    listed = client.get(TASKS_URL).json()["tasks"]

    assert listed[0]["deletable"] is False


def test_one_user_cannot_archive_another_user_task(client: TestClient) -> None:
    _register(client, email="first@example.com")
    task = _create(client, "First user's task")

    client.cookies.clear()
    _register(client, email="second@example.com")

    response = client.post(f"{TASKS_URL}/{task['id']}/archive")

    assert response.status_code == 404
    assert response.json()["code"] == "task_not_found"


def test_one_user_cannot_delete_another_user_task(client: TestClient) -> None:
    _register(client, email="first@example.com")
    task = _create(client, "First user's task")

    client.cookies.clear()
    _register(client, email="second@example.com")

    response = client.delete(f"{TASKS_URL}/{task['id']}")

    assert response.status_code == 404
    assert response.json()["code"] == "task_not_found"
