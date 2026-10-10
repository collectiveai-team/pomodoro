"""Unit tests for the History HTTP endpoints: month summary and day detail (T18)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from pomodoro.database.models.pomodoro import PomodoroTable
from sqlmodel import Session

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy import Engine

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
TASKS_URL = "/api/v1/tasks"
MONTH_URL = "/api/v1/history/month"
DAY_URL = "/api/v1/history/day"

# The default registered time zone is fixed at UTC-3 year-round (no DST), making the UTC
# instants below easy to reason about against local calendar days.
TIME_ZONE = "America/Argentina/Buenos_Aires"


def _register(client: TestClient, *, email: str = "owner@example.com") -> None:
    client.post(
        REGISTER_URL,
        json={"email": email, "password": "correct-horse-battery-staple", "time_zone": TIME_ZONE},
    )


def _create_task(  # ast-grep-ignore: no-dict-return-annotation
    client: TestClient, text: str
) -> dict:
    response = client.post(TASKS_URL, json={"text": text})
    assert response.status_code == 201
    return response.json()


def _set_tags(  # ast-grep-ignore: no-dict-return-annotation
    client: TestClient, task_id: str, names: list[str]
) -> dict:
    return client.patch(f"{TASKS_URL}/{task_id}/tags", json={"names": names}).json()


def _record_pomodoro(
    db_engine: Engine,
    *,
    user_id: UUID,
    task_id: UUID,
    ended_at: datetime,
    duration_seconds: int = 1500,
    status: str = "completed",
) -> None:
    with Session(db_engine) as session:
        session.add(
            PomodoroTable(
                user_id=user_id,
                task_id=task_id,
                started_at=ended_at,
                ended_at=ended_at,
                duration_seconds=duration_seconds,
                status=status,
            )
        )
        session.commit()


def test_month_summary_reports_every_day_with_zero_for_days_without_pomodoros(
    client: TestClient, db_engine: Engine
) -> None:
    _register(client)
    task = _create_task(client, "Write report")
    user_id = UUID(client.get("/api/v1/auth/me").json()["id"])

    # 2026-03-01 10:00 local (UTC-3) -> 2026-03-01 13:00 UTC.
    _record_pomodoro(
        db_engine,
        user_id=user_id,
        task_id=UUID(task["id"]),
        ended_at=datetime(2026, 3, 1, 13, tzinfo=UTC),
    )
    # 2026-03-15 10:00 local -> 2026-03-15 13:00 UTC, two completed Pomodoros.
    _record_pomodoro(
        db_engine,
        user_id=user_id,
        task_id=UUID(task["id"]),
        ended_at=datetime(2026, 3, 15, 13, tzinfo=UTC),
    )
    _record_pomodoro(
        db_engine,
        user_id=user_id,
        task_id=UUID(task["id"]),
        ended_at=datetime(2026, 3, 15, 14, tzinfo=UTC),
    )

    response = client.get(MONTH_URL, params={"year": 2026, "month": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["year"] == 2026
    assert body["month"] == 3
    assert len(body["days"]) == 31
    counts_by_day = {day["day"]: day["completed_count"] for day in body["days"]}
    assert counts_by_day["2026-03-01"] == 1
    assert counts_by_day["2026-03-15"] == 2
    assert counts_by_day["2026-03-02"] == 0


def test_month_summary_buckets_by_local_day_not_utc_day(
    client: TestClient, db_engine: Engine
) -> None:
    _register(client)
    task = _create_task(client, "Write report")
    user_id = UUID(client.get("/api/v1/auth/me").json()["id"])

    # 2026-03-01 01:00 UTC is 2026-02-28 22:00 local (UTC-3): the previous day and month.
    _record_pomodoro(
        db_engine,
        user_id=user_id,
        task_id=UUID(task["id"]),
        ended_at=datetime(2026, 3, 1, 1, tzinfo=UTC),
    )

    march = client.get(MONTH_URL, params={"year": 2026, "month": 3}).json()
    february = client.get(MONTH_URL, params={"year": 2026, "month": 2}).json()

    march_counts = {day["day"]: day["completed_count"] for day in march["days"]}
    february_counts = {day["day"]: day["completed_count"] for day in february["days"]}
    assert march_counts["2026-03-01"] == 0
    assert february_counts["2026-02-28"] == 1


def test_month_summary_is_scoped_to_the_caller_only(client: TestClient, db_engine: Engine) -> None:
    _register(client, email="first@example.com")
    first_task = _create_task(client, "First user's task")
    first_user_id = UUID(client.get("/api/v1/auth/me").json()["id"])
    _record_pomodoro(
        db_engine,
        user_id=first_user_id,
        task_id=UUID(first_task["id"]),
        ended_at=datetime(2026, 3, 1, 13, tzinfo=UTC),
    )

    client.cookies.clear()
    _register(client, email="second@example.com")

    response = client.get(MONTH_URL, params={"year": 2026, "month": 3})

    assert response.status_code == 200
    counts_by_day = {day["day"]: day["completed_count"] for day in response.json()["days"]}
    assert counts_by_day["2026-03-01"] == 0


def test_day_detail_mixes_completed_and_interrupted_pomodoros_per_task(
    client: TestClient, db_engine: Engine
) -> None:
    _register(client)
    task_a = _create_task(client, "Task A")
    task_b = _create_task(client, "Task B")
    user_id = UUID(client.get("/api/v1/auth/me").json()["id"])

    ended_at = datetime(2026, 3, 1, 13, tzinfo=UTC)
    _record_pomodoro(
        db_engine,
        user_id=user_id,
        task_id=UUID(task_a["id"]),
        ended_at=ended_at,
        status="completed",
    )
    _record_pomodoro(
        db_engine,
        user_id=user_id,
        task_id=UUID(task_a["id"]),
        ended_at=ended_at,
        duration_seconds=600,
        status="interrupted_logged",
    )
    _record_pomodoro(
        db_engine,
        user_id=user_id,
        task_id=UUID(task_b["id"]),
        ended_at=ended_at,
        status="completed",
    )

    response = client.get(DAY_URL, params={"date": "2026-03-01"})

    assert response.status_code == 200
    body = response.json()
    assert body["day"] == "2026-03-01"
    assert body["completed_count"] == 2
    tasks_by_id = {entry["task_id"]: entry for entry in body["tasks"]}
    assert tasks_by_id[task_a["id"]]["completed_count"] == 1
    assert tasks_by_id[task_a["id"]]["dedicated_seconds"] == 1500 + 600
    assert tasks_by_id[task_b["id"]]["completed_count"] == 1
    assert tasks_by_id[task_b["id"]]["dedicated_seconds"] == 1500


def test_day_detail_is_empty_for_a_day_with_no_pomodoros(client: TestClient) -> None:
    _register(client)

    response = client.get(DAY_URL, params={"date": "2026-03-02"})

    assert response.status_code == 200
    assert response.json() == {"day": "2026-03-02", "completed_count": 0, "tasks": []}


def test_day_detail_applies_the_shared_text_and_tag_filters(
    client: TestClient, db_engine: Engine
) -> None:
    _register(client)
    work_task = _create_task(client, "Write report")
    personal_task = _create_task(client, "Call dentist")
    work_tag_id = _set_tags(client, work_task["id"], ["Work"])["tag_ids"][0]
    user_id = UUID(client.get("/api/v1/auth/me").json()["id"])

    ended_at = datetime(2026, 3, 1, 13, tzinfo=UTC)
    _record_pomodoro(db_engine, user_id=user_id, task_id=UUID(work_task["id"]), ended_at=ended_at)
    _record_pomodoro(
        db_engine, user_id=user_id, task_id=UUID(personal_task["id"]), ended_at=ended_at
    )

    by_text = client.get(DAY_URL, params={"date": "2026-03-01", "q": "report"})
    by_tag = client.get(DAY_URL, params={"date": "2026-03-01", "tags": work_tag_id})

    assert [entry["task_id"] for entry in by_text.json()["tasks"]] == [work_task["id"]]
    assert [entry["task_id"] for entry in by_tag.json()["tasks"]] == [work_task["id"]]
