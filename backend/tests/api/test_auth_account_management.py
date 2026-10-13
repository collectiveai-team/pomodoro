"""Unit tests for change-password and delete-account (CES-4, CES-17; User Stories 9-10)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pomodoro.core.timer import TimerPhase
from pomodoro.database.models.auth_session import AuthSessionTable
from pomodoro.database.models.pomodoro import PomodoroTable
from pomodoro.database.models.tag import TagTable
from pomodoro.database.models.task import TaskTable
from pomodoro.database.models.task_tag import TaskTagTable
from pomodoro.database.models.timer import TimerTable
from pomodoro.database.models.user import UserTable
from sqlmodel import Session, select

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy import Engine

pytestmark = pytest.mark.unit

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
CHANGE_PASSWORD_URL = "/api/v1/auth/change-password"
EMAIL = "owner@example.com"
PASSWORD = "correct-horse-battery-staple"


def _register(client: TestClient, *, email: str = EMAIL, password: str = PASSWORD) -> None:
    response = client.post(
        REGISTER_URL,
        json={"email": email, "password": password, "time_zone": "America/Argentina/Buenos_Aires"},
    )
    assert response.status_code == 201


def _row_count(db_engine: Engine, table: type) -> int:
    with Session(db_engine) as session:
        return len(session.exec(select(table)).all())


def test_change_password_rejects_a_wrong_current_password(client: TestClient) -> None:
    _register(client)

    response = client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": "not-the-password", "new_password": "a-brand-new-password"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"

    # The password never changed: the original still logs in.
    login_response = client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert login_response.status_code == 200


def test_change_password_revokes_every_other_session_but_keeps_the_current_one(
    client: TestClient,
) -> None:
    _register(client)
    session_a = client.cookies.get("session")
    assert session_a

    client.cookies.clear()
    login_response = client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert login_response.status_code == 200
    session_b = client.cookies.get("session")
    assert session_b
    assert session_b != session_a

    client.cookies.set("session", session_a)
    change_response = client.post(
        CHANGE_PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": "a-brand-new-password"},
    )
    assert change_response.status_code == 204

    # The session used to change the password is untouched.
    assert client.get(ME_URL).status_code == 200

    # Every other session for this User is revoked.
    client.cookies.set("session", session_b)
    assert client.get(ME_URL).status_code == 401

    # The new password now authenticates; the old one no longer does.
    client.cookies.clear()
    assert client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD}).status_code == 401
    ok_response = client.post(LOGIN_URL, json={"email": EMAIL, "password": "a-brand-new-password"})
    assert ok_response.status_code == 200


def test_delete_account_rejects_a_wrong_password(client: TestClient) -> None:
    _register(client)

    response = client.request("DELETE", ME_URL, json={"password": "not-the-password"})

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"
    assert client.get(ME_URL).status_code == 200


def test_delete_account_cascades_every_owned_table_and_discards_an_in_progress_timer(
    client: TestClient, db_engine: Engine
) -> None:
    _register(client)

    task_response = client.post("/api/v1/tasks", json={"text": "Write the report"})
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]

    tag_response = client.patch(f"/api/v1/tasks/{task_id}/tags", json={"names": ["urgent"]})
    assert tag_response.status_code == 200

    start_response = client.post(
        "/api/v1/timer/start",
        json={"task_id": task_id, "expected_phase": TimerPhase.IDLE.value},
    )
    assert start_response.status_code == 200
    assert start_response.json()["phase"] == TimerPhase.POMODORO_RUNNING.value

    delete_response = client.request("DELETE", ME_URL, json={"password": PASSWORD})
    assert delete_response.status_code == 204

    assert client.get(ME_URL).status_code == 401

    for table in (
        UserTable,
        AuthSessionTable,
        TaskTable,
        TagTable,
        TaskTagTable,
        TimerTable,
        PomodoroTable,
    ):
        assert _row_count(db_engine, table) == 0, f"orphaned rows remain in {table.__tablename__}"
