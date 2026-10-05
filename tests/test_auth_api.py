"""HTTP-level tests for the auth endpoints: register/login/logout/me/change-password/delete-account.

`TestClient` dispatches each request on its own worker thread, and a
`sqlite:///:memory:` database is private to the connection that opened it, so
tests back the app with a `tmp_path` SQLite file instead, which every thread
can see.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from pomodoro.api import auth, session
from pomodoro.core.auth import hash_password
from pomodoro.core.entities import User, UserId
from pomodoro.core.normalization import normalize_key
from pomodoro.database import tables
from pomodoro.database.auth_session_repository import SQLAuthSessionRepository
from pomodoro.database.engine import session_scope
from pomodoro.database.user_repository import SQLUserRepository
from pomodoro.entrypoints.app import create_app
from sqlmodel import select

from tests.conftest import NOW, TEST_PASSWORD, FakeClock
from tests.conftest import http_test_engine as _engine

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.engine import Engine


def _build_client(engine: Engine, clock: FakeClock) -> TestClient:
    app = create_app()
    app.dependency_overrides.update(
        {
            session.get_clock: lambda: clock,
            session.get_user_repository: lambda: SQLUserRepository(engine),
            session.get_auth_session_repository: lambda: SQLAuthSessionRepository(engine, clock),
        }
    )
    return TestClient(app)


def _register(
    client: TestClient,
    *,
    email: str = "person@example.com",
    password: str = TEST_PASSWORD,
    time_zone: str = "America/Argentina/Buenos_Aires",
):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "time_zone": time_zone},
    )


def _login(client: TestClient, *, email: str = "person@example.com", password: str = TEST_PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _make_user(
    engine: Engine, *, email: str = "person@example.com", password: str = TEST_PASSWORD
) -> User:
    user = User(
        id=UserId(0),
        email=email,
        email_key=normalize_key(email),
        time_zone="UTC",
        notifications_enabled=True,
        alarm_enabled=True,
        created_at=NOW,
    )
    return SQLUserRepository(engine).add(user, password_hash=hash_password(password))


@dataclass
class _AuthedSession:
    """A ready-to-use client plus the state behind its cookie, for one test."""

    client: TestClient
    clock: FakeClock
    engine: Engine
    user: User
    cookies: dict[str, str]


def _authed_session(
    tmp_path: Path, *, email: str = "person@example.com", password: str = TEST_PASSWORD
) -> _AuthedSession:
    engine = _engine(tmp_path)
    clock = FakeClock()
    client = _build_client(engine, clock)
    response = _register(client, email=email, password=password)
    assert response.status_code == 201
    cookies = {session.SESSION_COOKIE_NAME: response.cookies[session.SESSION_COOKIE_NAME]}
    record = SQLUserRepository(engine).get_by_email_key(normalize_key(email))
    assert record is not None
    return _AuthedSession(
        client=client, clock=clock, engine=engine, user=record.user, cookies=cookies
    )


# --- register ------------------------------------------------------------------------


@pytest.mark.unit
def test_register_creates_user_logs_in_and_captures_time_zone(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    response = _register(client, time_zone="America/Argentina/Buenos_Aires")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "person@example.com"
    assert body["time_zone"] == "America/Argentina/Buenos_Aires"
    assert "password_hash" not in body
    assert session.SESSION_COOKIE_NAME in response.cookies

    cookie = response.cookies[session.SESSION_COOKIE_NAME]
    me_response = client.get("/api/auth/me", cookies={session.SESSION_COOKIE_NAME: cookie})
    assert me_response.status_code == 200
    assert me_response.json()["id"] == body["id"]


@pytest.mark.unit
def test_register_rejects_duplicate_email_case_and_whitespace_insensitive(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())
    assert _register(client, email=" Person@Example.com ").status_code == 201

    response = _register(client, email="person@example.com")

    assert response.status_code == 409


@pytest.mark.unit
def test_register_rejects_invalid_email_format(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    response = _register(client, email="not-an-email")

    assert response.status_code == 422


@pytest.mark.unit
def test_register_rejects_password_too_short(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    response = _register(client, password="short")

    assert response.status_code == 422


@pytest.mark.unit
def test_register_rejects_password_too_long(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    response = _register(client, password="a" * 129)

    assert response.status_code == 422


@pytest.mark.unit
def test_register_is_rate_limited_after_five_failed_attempts(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    for _ in range(5):
        assert _register(client, email="repeat@example.com", password="short").status_code == 422

    # Same IP + email key as the failures above, now blocked regardless of validity.
    response = _register(client, email="repeat@example.com")

    assert response.status_code == 429


@pytest.mark.unit
def test_register_rate_limit_is_scoped_per_email(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())
    for _ in range(5):
        assert _register(client, email="repeat@example.com", password="short").status_code == 422

    response = _register(client, email="someone-else@example.com")

    assert response.status_code == 201


# --- login ---------------------------------------------------------------------------


@pytest.mark.unit
def test_login_succeeds_and_sets_cookie(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    _make_user(engine)
    client = _build_client(engine, FakeClock())

    response = _login(client)

    assert response.status_code == 200
    assert response.json()["email"] == "person@example.com"
    assert session.SESSION_COOKIE_NAME in response.cookies


@pytest.mark.unit
def test_login_rejects_unknown_email_with_generic_message(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    response = _login(client, email="nobody@example.com")

    assert response.status_code == 401
    assert response.json()["detail"] == auth.GENERIC_LOGIN_ERROR


@pytest.mark.unit
def test_login_rejects_wrong_password_with_generic_message(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    _make_user(engine)
    client = _build_client(engine, FakeClock())

    response = _login(client, password="wrong password")

    assert response.status_code == 401
    assert response.json()["detail"] == auth.GENERIC_LOGIN_ERROR


@pytest.mark.unit
def test_login_is_rate_limited_after_five_failed_attempts(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    _make_user(engine)
    client = _build_client(engine, FakeClock())

    for _ in range(5):
        assert _login(client, password="wrong password").status_code == 401

    response = _login(client)  # correct credentials, but the bucket is blocked

    assert response.status_code == 429


@pytest.mark.unit
def test_login_rate_limit_resets_after_window_passes(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    _make_user(engine)
    clock = FakeClock()
    client = _build_client(engine, clock)
    for _ in range(5):
        assert _login(client, password="wrong password").status_code == 401
    assert _login(client).status_code == 429

    clock.advance(auth.DEFAULT_RATE_LIMIT_WINDOW.total_seconds() + 1)
    response = _login(client)

    assert response.status_code == 200


# --- logout --------------------------------------------------------------------------


@pytest.mark.unit
def test_logout_revokes_only_the_current_session(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    other_login = _login(s.client)
    other_cookies = {session.SESSION_COOKIE_NAME: other_login.cookies[session.SESSION_COOKIE_NAME]}
    assert other_cookies != s.cookies

    response = s.client.post("/api/auth/logout", cookies=s.cookies, json={})

    assert response.status_code == 204
    assert s.client.get("/api/auth/me", cookies=s.cookies).status_code == 401
    assert s.client.get("/api/auth/me", cookies=other_cookies).status_code == 200


# --- me --------------------------------------------------------------------------------


@pytest.mark.unit
def test_me_returns_only_public_fields(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.get("/api/auth/me", cookies=s.cookies)

    assert response.status_code == 200
    body = response.json()
    expected_fields = {
        "id",
        "email",
        "time_zone",
        "alarm_enabled",
        "notifications_enabled",
        "created_at",
    }
    assert set(body) == expected_fields


@pytest.mark.unit
def test_me_rejects_without_session(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    assert client.get("/api/auth/me").status_code == 401


# --- change-password -------------------------------------------------------------------


@pytest.mark.unit
def test_change_password_rejects_wrong_current_password(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.post(
        "/api/auth/change-password",
        cookies=s.cookies,
        json={"current_password": "wrong password", "new_password": "a new password"},
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_change_password_rejects_invalid_new_password_length(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.post(
        "/api/auth/change-password",
        cookies=s.cookies,
        json={"current_password": "correct horse", "new_password": "short"},
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_change_password_succeeds_and_revokes_other_sessions_but_keeps_current(
    tmp_path: Path,
) -> None:
    s = _authed_session(tmp_path)
    other_login = _login(s.client)
    other_cookies = {session.SESSION_COOKIE_NAME: other_login.cookies[session.SESSION_COOKIE_NAME]}

    response = s.client.post(
        "/api/auth/change-password",
        cookies=s.cookies,
        json={"current_password": "correct horse", "new_password": "a brand new password"},
    )

    assert response.status_code == 204
    assert s.client.get("/api/auth/me", cookies=s.cookies).status_code == 200
    assert s.client.get("/api/auth/me", cookies=other_cookies).status_code == 401

    relogin = _login(s.client, password="a brand new password")
    assert relogin.status_code == 200
    assert _login(s.client, password="correct horse").status_code == 401


# --- delete-account ----------------------------------------------------------------------


@pytest.mark.unit
def test_delete_account_rejects_wrong_password(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.post(
        "/api/auth/delete-account", cookies=s.cookies, json={"password": "wrong password"}
    )

    assert response.status_code == 422
    assert s.client.get("/api/auth/me", cookies=s.cookies).status_code == 200


@pytest.mark.unit
def test_delete_account_cascades_tasks_tags_pomodoros_timer_and_sessions(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    user_id = int(s.user.id)

    # Seed Task/Tag/Pomodoro/Timer rows directly: their SQL-backed repositories
    # don't exist yet (owned by later tickets), but delete-account must still
    # cascade them correctly, respecting pomodoro.task_id's ON DELETE RESTRICT.
    with session_scope(s.engine) as db:
        task = tables.Task(
            user_id=user_id,
            text="write report",
            text_key="write report",
            position=0,
            created_at=NOW,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.id is not None
        task_id = task.id

        tag = tables.Tag(user_id=user_id, name="work", name_key="work")
        db.add(tag)
        db.commit()
        db.refresh(tag)
        assert tag.id is not None
        tag_id = tag.id
        db.add(tables.TaskTag(task_id=task_id, tag_id=tag_id))

        db.add(
            tables.Pomodoro(
                user_id=user_id,
                task_id=task_id,
                started_at=NOW,
                ended_at=NOW + timedelta(minutes=25),
                duration_seconds=1500,
                status="completed",
            )
        )
        db.add(
            tables.Timer(
                user_id=user_id,
                phase="idle",
                task_id=task_id,
                accumulated_active_seconds=0,
            )
        )
        db.commit()

    response = s.client.post(
        "/api/auth/delete-account", cookies=s.cookies, json={"password": "correct horse"}
    )

    assert response.status_code == 204
    assert s.client.get("/api/auth/me", cookies=s.cookies).status_code == 401

    with session_scope(s.engine) as db:
        assert db.get(tables.User, user_id) is None
        assert db.get(tables.Task, task_id) is None
        assert db.get(tables.Tag, tag_id) is None
        assert (
            db.exec(select(tables.Pomodoro).where(tables.Pomodoro.user_id == user_id)).first()
            is None
        )
        assert db.get(tables.Timer, user_id) is None
        assert (
            db.exec(select(tables.TaskTag).where(tables.TaskTag.task_id == task_id)).first() is None
        )


# --- isolation -----------------------------------------------------------------------


def _register_two_users(client: TestClient) -> tuple[dict[str, str], dict[str, str]]:
    response_a = _register(client, email="a@example.com")
    response_b = _register(client, email="b@example.com")
    return (
        {session.SESSION_COOKIE_NAME: response_a.cookies[session.SESSION_COOKIE_NAME]},
        {session.SESSION_COOKIE_NAME: response_b.cookies[session.SESSION_COOKIE_NAME]},
    )


@pytest.mark.unit
def test_user_cannot_read_another_users_auth_data(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())
    cookies_a, cookies_b = _register_two_users(client)

    me_a = client.get("/api/auth/me", cookies=cookies_a)
    me_b = client.get("/api/auth/me", cookies=cookies_b)

    assert me_a.json()["email"] == "a@example.com"
    assert me_b.json()["email"] == "b@example.com"
    assert me_a.json()["id"] != me_b.json()["id"]


@pytest.mark.unit
def test_logging_out_one_user_does_not_affect_another_users_session(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())
    cookies_a, cookies_b = _register_two_users(client)

    assert client.post("/api/auth/logout", cookies=cookies_a, json={}).status_code == 204

    assert client.get("/api/auth/me", cookies=cookies_a).status_code == 401
    assert client.get("/api/auth/me", cookies=cookies_b).status_code == 200
