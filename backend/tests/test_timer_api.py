"""Tests for the T13 `api/v1/timer` router: get, actions, and the day summary.

Drives the real app (`entrypoints.app.create_app`) through `TestClient` over an
in-memory SQLite database (the `_in_memory_database`/`client`/`make_client`
conftest fixtures), never a mocked repository - matching T10's existing
`api/v1` test style. Scenarios that need an expired deadline backdate the
stored Timer row directly (`_seed_running`) instead of sleeping real time,
mirroring `test_tasks_api.py`'s `_seed_pomodoro`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func
from sqlmodel import Session, select

from pomodoro.core.timer import POMODORO_SECONDS
from pomodoro.database import tables
from pomodoro.database.tables import SQLModel
from pomodoro.entrypoints.dependencies import get_engine

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _schema(_in_memory_database: None) -> Engine:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    return engine


def _create_task(client: TestClient, text: str):
    return client.post("/api/v1/tasks", json={"text": text}).json()


def _post(client: TestClient, path: str):
    # The CSRF guard requires `Content-Type: application/json` on every mutation, even
    # a body-less POST - a real browser's `fetch` would set it explicitly too.
    return client.post(path, headers={"content-type": "application/json"})


def _pomodoro_count() -> int:
    with Session(get_engine()) as session:
        return session.exec(select(func.count()).select_from(tables.Pomodoro)).one()


def _seed_running(*, user_id: int, task_id: int, running_since: datetime) -> None:
    """Backdate a running Timer row directly, simulating time having passed."""
    with Session(get_engine()) as session:
        row = session.get(tables.Timer, user_id)
        if row is None:
            row = tables.Timer(user_id=user_id, phase="idle", version=0)
        row.phase = "pomodoro_running"
        row.task_id = task_id
        row.phase_started_at = running_since
        row.accumulated_active_seconds = 0
        row.running_since = running_since
        row.phase_ended_at = None
        session.add(row)
        session.commit()


def _seed_stopped(client: TestClient, *, task_id: int, active_seconds: int) -> None:
    """Seed a running Timer `active_seconds` in the past, then stop it (-> AskingToLog)."""
    started = datetime.now(UTC) - timedelta(seconds=active_seconds)
    _seed_running(
        user_id=client.get("/api/v1/auth/me").json()["id"], task_id=task_id, running_since=started
    )
    _post(client, "/api/v1/timer/stop")


def _seed_expired_and_settle(client: TestClient, *, task_id: int) -> None:
    """Seed a Pomodoro that expired while away, then settle it via a GET (-> ReadyForNext)."""
    started = datetime.now(UTC) - timedelta(seconds=POMODORO_SECONDS + 10)
    _seed_running(
        user_id=client.get("/api/v1/auth/me").json()["id"], task_id=task_id, running_since=started
    )
    client.get("/api/v1/timer")


class TestGetTimer:
    def test_a_fresh_timer_is_idle(self, client: TestClient) -> None:
        response = client.get("/api/v1/timer")

        assert response.status_code == 200
        body = response.json()
        assert body["phase"] == "idle"
        assert body["task_id"] is None
        assert body["remaining_seconds"] is None
        assert "server_now" in body

    def test_get_without_a_session_is_rejected(self, anonymous_client: TestClient) -> None:
        response = anonymous_client.get("/api/v1/timer")

        assert response.status_code == 401

    def test_get_settles_a_pomodoro_that_expired_while_away(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        started = datetime.now(UTC) - timedelta(seconds=POMODORO_SECONDS + 3600)
        _seed_running(
            user_id=client.get("/api/v1/auth/me").json()["id"],
            task_id=task["id"],
            running_since=started,
        )

        response = client.get("/api/v1/timer")

        assert response.status_code == 200
        body = response.json()
        assert body["phase"] == "ready_for_next"
        assert body["task_id"] == task["id"]
        assert _pomodoro_count() == 1


class TestStart:
    def test_starts_against_an_active_task(self, client: TestClient) -> None:
        task = _create_task(client, "Write")

        response = client.post("/api/v1/timer/start", json={"task_id": task["id"]})

        assert response.status_code == 200
        body = response.json()
        assert body["phase"] == "pomodoro_running"
        assert body["task_id"] == task["id"]
        assert body["remaining_seconds"] == POMODORO_SECONDS

    def test_rejects_an_unknown_task(self, client: TestClient) -> None:
        response = client.post("/api/v1/timer/start", json={"task_id": 999999})

        assert response.status_code == 404

    def test_rejects_an_archived_task(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _post(client, f"/api/v1/tasks/{task['id']}/archive")

        response = client.post("/api/v1/timer/start", json={"task_id": task["id"]})

        assert response.status_code == 400

    def test_rejects_another_users_task(
        self, client: TestClient, make_client: Callable[..., TestClient]
    ) -> None:
        other_task = _create_task(client, "Mine")
        other_user = make_client(email="other@example.com")

        response = other_user.post("/api/v1/timer/start", json={"task_id": other_task["id"]})

        assert response.status_code == 404

    def test_a_second_start_while_one_is_already_running_is_409_with_the_current_timer(
        self, client: TestClient
    ) -> None:
        task = _create_task(client, "Write")
        client.post("/api/v1/timer/start", json={"task_id": task["id"]})

        response = client.post("/api/v1/timer/start", json={"task_id": task["id"]})

        assert response.status_code == 409
        body = response.json()
        assert body["phase"] == "pomodoro_running"
        assert "detail" not in body  # the TimerResponse shape, not the generic ErrorResponse


class TestPauseResumeStop:
    def test_pause_then_resume_round_trips(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        client.post("/api/v1/timer/start", json={"task_id": task["id"]})

        paused = _post(client, "/api/v1/timer/pause")
        assert paused.status_code == 200
        assert paused.json()["phase"] == "pomodoro_paused"

        resumed = _post(client, "/api/v1/timer/resume")
        assert resumed.json()["phase"] == "pomodoro_running"

    def test_stop_moves_to_asking_to_log(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        client.post("/api/v1/timer/start", json={"task_id": task["id"]})

        response = _post(client, "/api/v1/timer/stop")

        assert response.status_code == 200
        assert response.json()["phase"] == "asking_to_log"


class TestLogAndDiscard:
    def test_log_persists_the_interrupted_pomodoro(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _seed_stopped(client, task_id=task["id"], active_seconds=600)

        response = _post(client, "/api/v1/timer/log")

        assert response.status_code == 200
        assert response.json()["phase"] == "idle"
        assert _pomodoro_count() == 1

    def test_logging_twice_records_the_pomodoro_once(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _seed_stopped(client, task_id=task["id"], active_seconds=600)

        first = _post(client, "/api/v1/timer/log")
        second = _post(client, "/api/v1/timer/log")

        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json()["phase"] == "idle"
        assert _pomodoro_count() == 1

    def test_discard_leaves_no_trace(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _seed_stopped(client, task_id=task["id"], active_seconds=600)

        response = _post(client, "/api/v1/timer/discard")

        assert response.status_code == 200
        assert response.json()["phase"] == "idle"
        assert _pomodoro_count() == 0


class TestActionPhaseMismatch:
    def test_pausing_an_idle_timer_is_409_with_the_current_timer(self, client: TestClient) -> None:
        response = _post(client, "/api/v1/timer/pause")

        assert response.status_code == 409
        body = response.json()
        assert body["phase"] == "idle"
        assert "detail" not in body

    def test_resuming_an_idle_timer_is_409(self, client: TestClient) -> None:
        response = _post(client, "/api/v1/timer/resume")

        assert response.status_code == 409

    def test_logging_with_nothing_to_log_is_409(self, client: TestClient) -> None:
        response = _post(client, "/api/v1/timer/log")

        assert response.status_code == 409


class TestBreakFlow:
    def test_start_break_then_skip_break_returns_to_idle(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _seed_expired_and_settle(client, task_id=task["id"])

        started_break = _post(client, "/api/v1/timer/start-break")
        assert started_break.status_code == 200
        assert started_break.json()["phase"] == "break_running"
        assert started_break.json()["break_kind"] == "short"

        skipped = _post(client, "/api/v1/timer/skip-break")
        assert skipped.status_code == 200
        assert skipped.json()["phase"] == "idle"

    def test_next_pomodoro_continues_the_same_task(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _seed_expired_and_settle(client, task_id=task["id"])

        response = _post(client, "/api/v1/timer/next-pomodoro")

        assert response.status_code == 200
        body = response.json()
        assert body["phase"] == "pomodoro_running"
        assert body["task_id"] == task["id"]


class TestDaySummary:
    def test_a_fresh_account_has_nothing_completed_and_a_full_countdown(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/v1/timer/day-summary")

        assert response.status_code == 200
        body = response.json()
        assert body["completed_today"] == 0
        assert body["remaining_to_long_break"] == 5

    def test_a_completed_pomodoro_from_lazy_settlement_counts_today(
        self, client: TestClient
    ) -> None:
        task = _create_task(client, "Write")
        _seed_expired_and_settle(client, task_id=task["id"])

        response = client.get("/api/v1/timer/day-summary")

        assert response.status_code == 200
        body = response.json()
        assert body["completed_today"] == 1
        assert body["remaining_to_long_break"] == 4

    def test_day_summary_without_a_session_is_rejected(self, anonymous_client: TestClient) -> None:
        response = anonymous_client.get("/api/v1/timer/day-summary")

        assert response.status_code == 401
