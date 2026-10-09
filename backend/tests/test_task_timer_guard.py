"""Tests for the T14 Task/Timer interaction guard: archive/delete while in progress.

Core-level tests drive `core.tasks.ensure_task_not_in_progress` directly, pure
and DB-free (matching `test_core_tasks.py`'s style). API-level tests drive the
real app through `TestClient` over an in-memory SQLite database, reaching every
Timer phase through the real `api/v1/timer` actions rather than seeding a
Timer row directly, so each scenario also proves the guard genuinely blocks
the route, not just the underlying core rule.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlmodel import Session

from pomodoro.core.entities import BreakKind, Task, TaskId, Timer, TimerPhase, UserId
from pomodoro.core.errors import TaskInProgressError
from pomodoro.core.tasks import ensure_task_not_in_progress
from pomodoro.core.timer import POMODORO_SECONDS
from pomodoro.database import tables
from pomodoro.entrypoints.dependencies import get_engine

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_USER = UserId(1)


def _task(*, task_id: int = 1) -> Task:
    return Task(id=TaskId(task_id), user_id=_USER, text="Write", position=0, created_at=_NOW)


def _timer(*, phase: TimerPhase, task_id: int | None, break_kind: BreakKind | None = None) -> Timer:
    return Timer(
        user_id=_USER,
        phase=phase,
        task_id=TaskId(task_id) if task_id is not None else None,
        break_kind=break_kind,
    )


class TestEnsureTaskNotInProgress:
    @pytest.mark.parametrize(
        "phase",
        [
            TimerPhase.POMODORO_RUNNING,
            TimerPhase.POMODORO_PAUSED,
            TimerPhase.ASKING_TO_LOG,
            TimerPhase.READY_FOR_NEXT,
        ],
    )
    def test_raises_when_the_timer_is_currently_dedicated_to_this_task(
        self, phase: TimerPhase
    ) -> None:
        task = _task()
        timer = _timer(phase=phase, task_id=task.id)

        with pytest.raises(TaskInProgressError):
            ensure_task_not_in_progress(task, timer=timer)

    def test_allows_when_the_timer_is_idle(self) -> None:
        task = _task()
        timer = _timer(phase=TimerPhase.IDLE, task_id=None)

        assert ensure_task_not_in_progress(task, timer=timer) is None

    def test_allows_when_the_timer_is_on_a_break(self) -> None:
        task = _task()
        timer = _timer(phase=TimerPhase.BREAK_RUNNING, task_id=None, break_kind=BreakKind.SHORT)

        assert ensure_task_not_in_progress(task, timer=timer) is None

    def test_allows_when_the_timer_references_a_different_task(self) -> None:
        task = _task(task_id=1)
        timer = _timer(phase=TimerPhase.POMODORO_RUNNING, task_id=2)

        assert ensure_task_not_in_progress(task, timer=timer) is None


@pytest.fixture(autouse=True)
def _apply_schema(_schema: Engine) -> None:
    """Force the conftest `_schema` fixture (table creation) to run for every test here."""


def _create_task(client: TestClient, text: str):
    return client.post("/api/v1/tasks", json={"text": text}).json()


def _start(client: TestClient, task_id: int):
    return client.post("/api/v1/timer/start", json={"task_id": task_id})


def _post(client: TestClient, path: str):
    # The CSRF guard requires `Content-Type: application/json` on every mutation, even
    # a body-less POST - a real browser's `fetch` would set it explicitly too.
    return client.post(path, headers={"content-type": "application/json"})


def _stop_then_discard(client: TestClient) -> None:
    _post(client, "/api/v1/timer/stop")
    _post(client, "/api/v1/timer/discard")


def _archive(client: TestClient, task_id: object):
    return client.post(
        f"/api/v1/tasks/{task_id}/archive", headers={"content-type": "application/json"}
    )


def _delete(client: TestClient, task_id: object):
    return client.delete(f"/api/v1/tasks/{task_id}", headers={"content-type": "application/json"})


def _backdate_running_since(user_id: int, *, seconds_ago: int) -> None:
    """Push a started Pomodoro's `running_since`/`phase_started_at` into the past.

    `start()` sets both to the same instant; backdating only one would leave a
    completed Pomodoro's `ended_at` earlier than its `started_at`.
    """
    with Session(get_engine()) as session:
        row = session.get(tables.Timer, user_id)
        assert row is not None
        started = datetime.now(UTC) - timedelta(seconds=seconds_ago)
        row.running_since = started
        row.phase_started_at = started
        session.add(row)
        session.commit()


class TestArchiveGuard:
    def test_archiving_the_in_progress_task_is_rejected(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _start(client, task["id"])

        response = _archive(client, task["id"])

        assert response.status_code == 400
        assert "in progress" in response.json()["detail"].lower()

    def test_archiving_a_different_task_while_one_is_running_is_allowed(
        self, client: TestClient
    ) -> None:
        running = _create_task(client, "Running")
        other = _create_task(client, "Other")
        _start(client, running["id"])

        response = _archive(client, other["id"])

        assert response.status_code == 200

    def test_archiving_is_still_rejected_while_asking_to_log(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _start(client, task["id"])
        _post(client, "/api/v1/timer/stop")

        response = _archive(client, task["id"])

        assert response.status_code == 400

    def test_archiving_releases_once_the_timer_returns_to_idle(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _start(client, task["id"])
        _stop_then_discard(client)

        response = _archive(client, task["id"])

        assert response.status_code == 200

    def test_archiving_an_unrelated_task_settles_an_expired_pomodoro_at_request_time(
        self, client: TestClient
    ) -> None:
        """The guard must read a freshly settled Timer, not a stale cached phase (T14).

        Archiving `other` settles `running`'s already-expired Pomodoro as a side
        effect (visible in the day summary), and `running` stays blocked
        afterward since ReadyForNext keeps its task_id.
        """
        running = _create_task(client, "Running")
        other = _create_task(client, "Other")
        _start(client, running["id"])
        user_id = client.get("/api/v1/auth/me").json()["id"]
        _backdate_running_since(user_id, seconds_ago=POMODORO_SECONDS + 10)

        response = _archive(client, other["id"])

        assert response.status_code == 200
        summary = client.get("/api/v1/timer/day-summary").json()
        assert summary["completed_today"] == 1

        still_blocked = _archive(client, running["id"])
        assert still_blocked.status_code == 400

    def test_archiving_an_unknown_task_while_the_timer_is_running_is_still_a_404(
        self, client: TestClient
    ) -> None:
        task = _create_task(client, "Write")
        _start(client, task["id"])

        response = _archive(client, 999999)

        assert response.status_code == 404


class TestDeleteGuard:
    def test_deleting_the_in_progress_task_is_rejected(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _start(client, task["id"])

        response = _delete(client, task["id"])

        assert response.status_code == 400
        assert "in progress" in response.json()["detail"].lower()

    def test_deleting_a_different_task_while_one_is_running_is_allowed(
        self, client: TestClient
    ) -> None:
        running = _create_task(client, "Running")
        other = _create_task(client, "Other")
        _start(client, running["id"])

        response = _delete(client, other["id"])

        assert response.status_code == 204

    def test_deleting_releases_once_the_timer_returns_to_idle(self, client: TestClient) -> None:
        task = _create_task(client, "Write")
        _start(client, task["id"])
        _stop_then_discard(client)

        response = _delete(client, task["id"])

        assert response.status_code == 204
