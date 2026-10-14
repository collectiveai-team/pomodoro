"""Unit tests for GET /api/v1/tasks/{task_id}/history (issue #19, T5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from pomodoro.database.models.pomodoro import PomodoroTable
from sqlmodel import Session
from tests.conftest import create_task, register_user

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy import Engine

pytestmark = pytest.mark.unit

TASKS_URL = "/api/v1/tasks"


def _history_url(task_id: str | UUID) -> str:
    return f"{TASKS_URL}/{task_id}/history"


def _record(
    db_engine: Engine,
    *,
    user_id: UUID,
    task_id: str,
    ended_at: datetime,
    duration_seconds: int = 1500,
    status: str = "completed",
) -> None:
    with Session(db_engine) as session:
        session.add(
            PomodoroTable(
                user_id=user_id,
                task_id=UUID(task_id),
                started_at=ended_at,
                ended_at=ended_at,
                duration_seconds=duration_seconds,
                status=status,
            )
        )
        session.commit()


def _current_user_id(client: TestClient) -> UUID:
    return UUID(client.get("/api/v1/auth/me").json()["id"])


def test_history_totals_and_days_for_completed_and_interrupted_pomodoros(
    client: TestClient, db_engine: Engine
) -> None:
    register_user(client)
    task_id = create_task(client, "Write report")
    user_id = _current_user_id(client)
    # Buenos Aires is UTC-3: 13:00 UTC is 10:00 local on the same calendar day.
    _record(
        db_engine, user_id=user_id, task_id=task_id, ended_at=datetime(2026, 3, 1, 13, tzinfo=UTC)
    )
    _record(
        db_engine, user_id=user_id, task_id=task_id, ended_at=datetime(2026, 3, 5, 13, tzinfo=UTC)
    )
    _record(
        db_engine,
        user_id=user_id,
        task_id=task_id,
        ended_at=datetime(2026, 3, 5, 15, tzinfo=UTC),
        duration_seconds=600,
        status="interrupted_logged",
    )

    response = client.get(_history_url(task_id))

    assert response.status_code == 200
    assert response.json() == {
        "completed_count": 2,
        "dedicated_seconds": 3600,
        "first_day": "2026-03-01",
        "last_day": "2026-03-05",
        "active_days": 2,
        "days": [
            {"day": "2026-03-05", "completed_count": 1, "dedicated_seconds": 2100},
            {"day": "2026-03-01", "completed_count": 1, "dedicated_seconds": 1500},
        ],
    }


def test_history_buckets_days_in_the_users_time_zone(client: TestClient, db_engine: Engine) -> None:
    register_user(client)
    task_id = create_task(client, "Late night")
    # 01:00 UTC on March 2nd is 22:00 local on March 1st.
    _record(
        db_engine,
        task_id=task_id,
        user_id=_current_user_id(client),
        ended_at=datetime(2026, 3, 2, 1, tzinfo=UTC),
    )

    body = client.get(_history_url(task_id)).json()

    assert body["first_day"] == "2026-03-01"
    assert body["last_day"] == "2026-03-01"


def test_history_works_for_an_archived_task(client: TestClient, db_engine: Engine) -> None:
    register_user(client)
    task_id = create_task(client, "Old work")
    _record(
        db_engine,
        user_id=_current_user_id(client),
        task_id=task_id,
        ended_at=datetime(2026, 3, 1, 13, tzinfo=UTC),
    )
    assert client.post(f"{TASKS_URL}/{task_id}/archive").status_code == 200

    response = client.get(_history_url(task_id))

    assert response.status_code == 200
    assert response.json()["completed_count"] == 1


def test_history_of_a_task_without_pomodoros_is_empty(client: TestClient) -> None:
    register_user(client)
    task_id = create_task(client, "Untouched")

    response = client.get(_history_url(task_id))

    assert response.status_code == 200
    assert response.json() == {
        "completed_count": 0,
        "dedicated_seconds": 0,
        "first_day": None,
        "last_day": None,
        "active_days": 0,
        "days": [],
    }


def test_history_ignores_pomodoros_of_other_tasks(client: TestClient, db_engine: Engine) -> None:
    register_user(client)
    task_id = create_task(client, "Mine")
    other_id = create_task(client, "Other")
    _record(
        db_engine,
        user_id=_current_user_id(client),
        task_id=other_id,
        ended_at=datetime(2026, 3, 1, 13, tzinfo=UTC),
    )

    assert client.get(_history_url(task_id)).json()["completed_count"] == 0


def test_history_of_another_users_task_is_404(client: TestClient) -> None:
    register_user(client, email="first@example.com")
    foreign_task_id = create_task(client, "First user's task")
    client.post("/api/v1/auth/logout")
    register_user(client, email="second@example.com")

    response = client.get(_history_url(foreign_task_id))

    assert response.status_code == 404
    assert response.json()["code"] == "task_not_found"


def test_history_of_a_missing_task_is_404(client: TestClient) -> None:
    register_user(client)

    response = client.get(_history_url(uuid4()))

    assert response.status_code == 404
    assert response.json()["code"] == "task_not_found"
