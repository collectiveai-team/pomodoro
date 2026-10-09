"""Tests for the T9 `api/v1/auth` router: every story in the spec's 'Registro y cuenta' section.

Drives the real app (`entrypoints.app.create_app`) through `TestClient` over an
in-memory SQLite database (the `_in_memory_database` conftest fixture), never a
mocked repository - matching T7/T8's existing `api/v1` test style.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from pomodoro.database import tables
from pomodoro.database.tables import SQLModel
from pomodoro.entrypoints.app import create_app
from pomodoro.entrypoints.dependencies import get_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

pytestmark = pytest.mark.unit

# Normalized form: `core.auth.normalize_email` lowercases the domain (RFC 5321 is
# case-insensitive there) but preserves local-part case, so a literal mixed-case
# address would never round-trip back unchanged through register/login/me.
_EMAIL = "someone@example.com"
_PASSWORD = "correct horse battery staple"
_TIME_ZONE = "America/Bogota"


@pytest.fixture(autouse=True)
def _schema(_in_memory_database: None) -> Engine:
    # Explicitly depend on the conftest autouse fixture so it runs first: it sets
    # DATABASE_URL and clears the cached engine (mirrors test_session_infra.py).
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    return engine


def _client() -> TestClient:
    # `set_session_cookie` sets `Secure`, as the spec requires - which means a plain
    # `http://testserver` TestClient would store the cookie but never resend it (the same
    # rule a real browser follows). `https://testserver` makes the round trip work in tests
    # without weakening the cookie itself.
    return TestClient(create_app(), base_url="https://testserver")


@pytest.fixture
def client() -> TestClient:
    return _client()


def _register(
    client: TestClient,
    *,
    email: str = _EMAIL,
    password: str = _PASSWORD,
    time_zone: str = _TIME_ZONE,
):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "time_zone": time_zone},
    )


def _login(client: TestClient, *, email: str = _EMAIL, password: str = _PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


class TestRegister:
    def test_registering_logs_the_user_in_and_sets_the_session_cookie(
        self, client: TestClient
    ) -> None:
        response = _register(client)

        assert response.status_code == 201
        assert "session" in response.cookies
        body = response.json()
        assert body["email"] == _EMAIL
        assert body["time_zone"] == _TIME_ZONE
        assert "password_hash" not in body
        assert "email_key" not in body

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == _EMAIL

    @pytest.mark.parametrize("duplicate_email", ["Someone@Example.com", "someone@example.com  "])
    def test_rejects_a_normalized_duplicate_email(
        self, client: TestClient, duplicate_email: str
    ) -> None:
        _register(client)

        response = _register(client, email=duplicate_email)

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_rejects_a_syntactically_invalid_email(self, client: TestClient) -> None:
        response = _register(client, email="not-an-email")

        assert response.status_code == 400

    def test_rejects_a_password_shorter_than_the_minimum(self, client: TestClient) -> None:
        response = _register(client, password="short1")

        assert response.status_code == 400
        assert "short1" not in response.text

    def test_rejects_a_password_longer_than_the_maximum(self, client: TestClient) -> None:
        response = _register(client, password="a" * 129)

        assert response.status_code == 400

    def test_rejects_an_invalid_time_zone(self, client: TestClient) -> None:
        response = _register(client, time_zone="Mars/Olympus_Mons")

        assert response.status_code == 400

    def test_persists_the_browser_supplied_time_zone(self, client: TestClient) -> None:
        _register(client, time_zone="Europe/Madrid")

        me = client.get("/api/v1/auth/me")

        assert me.json()["time_zone"] == "Europe/Madrid"

    def test_rate_limits_after_five_failed_attempts_from_the_same_ip_and_email(
        self, client: TestClient
    ) -> None:
        # Spec story 12 requires rate limiting on both "login y registro": a duplicate
        # email is register's own failure mode (mirrors TestLogin's wrong-password case),
        # recorded by the same `enforce_login_rate_limit`/`record_failure` pair.
        _register(client)

        for _ in range(5):
            _register(client)

        response = _register(client)

        assert response.status_code == 429


class TestLogin:
    def test_logs_in_with_correct_credentials(self, client: TestClient) -> None:
        _register(client)
        client.cookies.clear()

        response = _login(client)

        assert response.status_code == 200
        assert "session" in response.cookies
        assert response.json()["email"] == _EMAIL

    def test_unknown_email_and_wrong_password_share_the_same_generic_message(
        self, client: TestClient
    ) -> None:
        _register(client)
        client.cookies.clear()

        unknown_email = _login(client, email="nobody@example.com")
        wrong_password = _login(client, password="totally wrong password")

        assert unknown_email.status_code == 401
        assert wrong_password.status_code == 401
        assert unknown_email.json()["detail"] == wrong_password.json()["detail"]
        assert unknown_email.json()["detail"] == "email o contraseña incorrectos"

    def test_rate_limits_after_five_failed_attempts_from_the_same_ip_and_email(
        self, client: TestClient
    ) -> None:
        _register(client)
        client.cookies.clear()

        for _ in range(5):
            _login(client, password="wrong password entirely")

        response = _login(client, password="wrong password entirely")

        assert response.status_code == 429

    def test_a_different_email_is_not_blocked_by_another_emails_failures(
        self, client: TestClient
    ) -> None:
        _register(client)
        _register(client, email="other@example.com")
        client.cookies.clear()

        for _ in range(5):
            _login(client, password="wrong password entirely")

        response = _login(client, email="other@example.com")

        assert response.status_code == 200


class TestLogout:
    def test_logout_revokes_only_the_current_session(self) -> None:
        client_a = _client()
        _register(client_a)
        client_b = _client()
        _login(client_b)

        client_a.post("/api/v1/auth/logout", json={})

        assert client_a.get("/api/v1/auth/me").status_code == 401
        assert client_b.get("/api/v1/auth/me").status_code == 200

    def test_logout_without_a_session_is_rejected(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/logout", json={})

        assert response.status_code == 401


class TestMe:
    def test_me_without_a_session_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/v1/auth/me").status_code == 401


class TestChangePassword:
    def _register_two_sessions(self, email: str = _EMAIL) -> tuple[TestClient, TestClient]:
        primary = _client()
        _register(primary, email=email)
        secondary = _client()
        _login(secondary, email=email)
        return primary, secondary

    def test_rejects_an_incorrect_current_password(self, client: TestClient) -> None:
        _register(client)

        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "wrong password entirely", "new_password": "new password!"},
        )

        assert response.status_code == 401

    def test_revokes_every_other_session_but_keeps_the_current_one(self) -> None:
        primary, secondary = self._register_two_sessions()

        response = primary.post(
            "/api/v1/auth/change-password",
            json={"current_password": _PASSWORD, "new_password": "a brand new password"},
        )

        assert response.status_code == 204
        assert primary.get("/api/v1/auth/me").status_code == 200
        assert secondary.get("/api/v1/auth/me").status_code == 401

    def test_the_new_password_can_log_in_afterward(self, client: TestClient) -> None:
        _register(client)
        new_password = "a brand new password"
        client.post(
            "/api/v1/auth/change-password",
            json={"current_password": _PASSWORD, "new_password": new_password},
        )
        client.cookies.clear()

        response = _login(client, password=new_password)

        assert response.status_code == 200

    def test_change_password_without_a_session_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": _PASSWORD, "new_password": "whatever new"},
        )

        assert response.status_code == 401


class TestDeleteAccount:
    def test_rejects_an_incorrect_password(self, client: TestClient) -> None:
        _register(client)

        response = client.post(
            "/api/v1/auth/delete-account", json={"password": "wrong password entirely"}
        )

        assert response.status_code == 401

    def test_deletes_the_account_and_every_dependent_row(self, client: TestClient) -> None:
        register_response = _register(client)
        user_id = register_response.json()["id"]
        with Session(get_engine()) as session:
            _seed_full_account(session, user_id=user_id)

        response = client.post("/api/v1/auth/delete-account", json={"password": _PASSWORD})

        assert response.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401
        with Session(get_engine()) as session:
            assert session.get(tables.User, user_id) is None
            assert (
                session.exec(
                    select(tables.AuthSession).where(tables.AuthSession.user_id == user_id)
                ).all()
                == []
            )
            assert (
                session.exec(select(tables.Timer).where(tables.Timer.user_id == user_id)).all()
                == []
            )
            assert (
                session.exec(
                    select(tables.Pomodoro).where(tables.Pomodoro.user_id == user_id)
                ).all()
                == []
            )
            assert session.exec(select(tables.Tag).where(tables.Tag.user_id == user_id)).all() == []
            assert (
                session.exec(select(tables.Task).where(tables.Task.user_id == user_id)).all() == []
            )

    def test_delete_account_without_a_session_is_rejected(self, client: TestClient) -> None:
        response = client.post("/api/v1/auth/delete-account", json={"password": _PASSWORD})

        assert response.status_code == 401


class TestCrossUserIsolation:
    def test_changing_one_users_password_never_touches_another_users(self) -> None:
        user_a = _client()
        _register(user_a, email="a@example.com")
        user_b = _client()
        _register(user_b, email="b@example.com")

        user_a.post(
            "/api/v1/auth/change-password",
            json={"current_password": _PASSWORD, "new_password": "a new password for a"},
        )

        # User B's own password and session are untouched by A's change.
        assert user_b.get("/api/v1/auth/me").status_code == 200
        user_b.cookies.clear()
        assert _login(user_b, email="b@example.com").status_code == 200

    def test_deleting_one_users_account_never_touches_another_users(self) -> None:
        user_a = _client()
        _register(user_a, email="a@example.com")
        user_b = _client()
        _register(user_b, email="b@example.com")

        user_a.post("/api/v1/auth/delete-account", json={"password": _PASSWORD})

        assert user_b.get("/api/v1/auth/me").status_code == 200

    def test_me_returns_only_the_authenticated_users_own_data(self) -> None:
        user_a = _client()
        _register(user_a, email="a@example.com")
        user_b = _client()
        _register(user_b, email="b@example.com")

        assert user_a.get("/api/v1/auth/me").json()["email"] == "a@example.com"
        assert user_b.get("/api/v1/auth/me").json()["email"] == "b@example.com"


class TestCsrfGuard:
    def test_a_mutation_without_json_content_type_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login",
            data="email=a&password=b",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 403


def _seed_full_account(session: Session, *, user_id: int) -> None:
    now = datetime.now(UTC)
    task = tables.Task(user_id=user_id, text="Write", text_key="write", position=0, created_at=now)
    session.add(task)
    session.commit()
    session.refresh(task)
    assert task.id is not None

    tag = tables.Tag(user_id=user_id, name="Work", name_key="work")
    session.add(tag)
    session.commit()
    session.refresh(tag)
    assert tag.id is not None
    session.add(tables.TaskTags(task_id=task.id, tag_id=tag.id))

    session.add(
        tables.Pomodoro(
            user_id=user_id,
            task_id=task.id,
            started_at=now - timedelta(minutes=25),
            ended_at=now,
            duration_seconds=1500,
            status="completed",
        )
    )
    # `task_id` set, like `pomodoro.task_id` above: both are RESTRICT, so deleting this
    # account only works if the cascade clears Timer/Pomodoro before it reaches Task.
    session.add(tables.Timer(user_id=user_id, phase="pomodoro_running", task_id=task.id))
    session.commit()
