"""HTTP-level tests for the session cookie lifecycle, `require_session`, and CSRF guard.

A throwaway protected router is mounted only in this test module (never on the
production app) to exercise `require_session` before any real feature route
exists.

Uses a `tmp_path` SQLite file rather than `sqlite:///:memory:`: `TestClient`
dispatches each request on a worker thread, and SQLite's `:memory:` database is
private to the connection that created it, so a second thread would see an
empty (tableless) database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated

import pytest
from fastapi import APIRouter, Depends, Response
from fastapi.testclient import TestClient
from pomodoro.api import session
from pomodoro.core.auth import generate_session_token, hash_session_token
from pomodoro.core.entities import AuthSession, User, UserId
from pomodoro.core.normalization import normalize_key
from pomodoro.database.auth_session_repository import SQLAuthSessionRepository
from pomodoro.database.engine import create_db_engine
from pomodoro.database.tables import SQLModel
from pomodoro.database.user_repository import SQLUserRepository
from pomodoro.entrypoints.app import create_app

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.engine import Engine

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class FakeClock:
    """A `Clock` advanced by hand, standing in for the real wall clock in tests."""

    current: datetime = NOW

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> datetime:
        self.current += timedelta(seconds=seconds)
        return self.current


_protected_router = APIRouter()


@_protected_router.get("/test/protected")
def _protected_get(user: Annotated[User, Depends(session.require_session)]) -> int:
    return user.id


@_protected_router.post("/test/protected")
def _protected_post(user: Annotated[User, Depends(session.require_session)]) -> int:
    return user.id


def _engine(tmp_path: Path) -> Engine:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'pomodoro.db'}")
    SQLModel.metadata.create_all(engine)
    return engine


def _build_client(engine: Engine, clock: FakeClock) -> TestClient:
    app = create_app()
    app.dependency_overrides[session.get_clock] = lambda: clock
    app.dependency_overrides[session.get_user_repository] = lambda: SQLUserRepository(engine)
    app.dependency_overrides[session.get_auth_session_repository] = lambda: (
        SQLAuthSessionRepository(engine, clock)
    )
    app.include_router(_protected_router)
    return TestClient(app)


def _make_user(engine: Engine, *, email: str = "person@example.com") -> User:
    user = User(
        id=UserId(0),
        email=email,
        email_key=normalize_key(email),
        created_at=NOW,
        time_zone="UTC",
        alarm_enabled=True,
        notifications_enabled=True,
    )
    return SQLUserRepository(engine).add(user, password_hash="argon2-hash")


def _create_session(engine: Engine, clock: FakeClock, user: User, *, expires_at: datetime) -> str:
    token = generate_session_token()
    SQLAuthSessionRepository(engine, clock).create(
        user.id, token_hash=hash_session_token(token), expires_at=expires_at
    )
    return token


@dataclass
class _AuthedSession:
    """A ready-to-use client plus the state behind its cookie, for one test."""

    client: TestClient
    clock: FakeClock
    engine: Engine
    user: User
    token: str


def _authed_session(tmp_path: Path, *, expires_at: datetime | None = None) -> _AuthedSession:
    engine = _engine(tmp_path)
    clock = FakeClock()
    user = _make_user(engine)
    token = _create_session(engine, clock, user, expires_at=expires_at or NOW + timedelta(days=30))
    return _AuthedSession(
        client=_build_client(engine, clock), clock=clock, engine=engine, user=user, token=token
    )


def _stored_session(s: _AuthedSession) -> AuthSession | None:
    repo = SQLAuthSessionRepository(s.engine, s.clock)
    return repo.get_by_token_hash(hash_session_token(s.token))


# --- cookie attributes -------------------------------------------------------------


@pytest.mark.unit
def test_set_session_cookie_sets_required_attributes() -> None:
    response = Response()

    session.set_session_cookie(response, "the-token")

    set_cookie = response.headers["set-cookie"]
    assert "session_token=the-token" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    assert f"Max-Age={int(session.SESSION_TTL.total_seconds())}" in set_cookie


# --- require_session: cookie presence and validity ----------------------------------


@pytest.mark.unit
def test_require_session_rejects_missing_cookie(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    response = client.get("/test/protected")

    assert response.status_code == 401


@pytest.mark.unit
def test_require_session_rejects_token_matching_no_session(tmp_path: Path) -> None:
    client = _build_client(_engine(tmp_path), FakeClock())

    response = client.get("/test/protected", cookies={session.SESSION_COOKIE_NAME: "garbage"})

    assert response.status_code == 401


@pytest.mark.unit
def test_require_session_accepts_valid_cookie(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.get("/test/protected", cookies={session.SESSION_COOKIE_NAME: s.token})

    assert response.status_code == 200
    assert response.json() == s.user.id


@pytest.mark.unit
def test_require_session_rejects_expired_session(tmp_path: Path) -> None:
    s = _authed_session(tmp_path, expires_at=NOW - timedelta(seconds=1))

    response = s.client.get("/test/protected", cookies={session.SESSION_COOKIE_NAME: s.token})

    assert response.status_code == 401


@pytest.mark.unit
def test_require_session_rejects_revoked_session(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)
    session_repo = SQLAuthSessionRepository(s.engine, s.clock)
    revoked = session_repo.get_by_token_hash(hash_session_token(s.token))
    assert revoked is not None
    session_repo.revoke(revoked.id)

    response = s.client.get("/test/protected", cookies={session.SESSION_COOKIE_NAME: s.token})

    assert response.status_code == 401


# --- require_session: sliding renewal -----------------------------------------------


@pytest.mark.unit
def test_require_session_renews_last_used_and_expiry_past_threshold(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    s.clock.advance(session.SESSION_RENEWAL_THRESHOLD.total_seconds() + 1)
    response = s.client.get("/test/protected", cookies={session.SESSION_COOKIE_NAME: s.token})

    assert response.status_code == 200
    renewed = _stored_session(s)
    assert renewed is not None
    assert renewed.last_used_at == s.clock.current
    assert renewed.expires_at == s.clock.current + session.SESSION_TTL


@pytest.mark.unit
def test_require_session_does_not_renew_before_threshold(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    s.clock.advance(60)  # well under the 1-hour renewal threshold
    response = s.client.get("/test/protected", cookies={session.SESSION_COOKIE_NAME: s.token})

    assert response.status_code == 200
    unchanged = _stored_session(s)
    assert unchanged is not None
    assert unchanged.last_used_at == NOW  # no DB write triggered below the threshold


# --- CSRF guard ----------------------------------------------------------------------


@pytest.mark.unit
def test_csrf_guard_rejects_mutating_request_without_json_content_type(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    response = s.client.post(
        "/test/protected",
        cookies={session.SESSION_COOKIE_NAME: s.token},
        content=b"not json",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 415


@pytest.mark.unit
def test_csrf_guard_accepts_mutating_request_with_json_content_type(tmp_path: Path) -> None:
    s = _authed_session(tmp_path)

    cookies = {session.SESSION_COOKIE_NAME: s.token}
    response = s.client.post("/test/protected", cookies=cookies, json={})

    assert response.status_code == 200
    assert response.json() == s.user.id
