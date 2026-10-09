"""Tests for the T8 session/auth-required infrastructure.

Covers `core.rate_limit.RateLimiter` directly (framework-free), then the
cookie/CSRF/IP/session-resolution helpers through a real FastAPI app via
`TestClient`, exactly like `test_app_factory.py`'s throwaway-router pattern.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlmodel import Session

from pomodoro.api.v1.session import (
    SESSION_COOKIE_NAME,
    SESSION_RENEWAL_THRESHOLD,
    enforce_login_rate_limit,
    require_json_content_type,
    resolve_client_ip,
)
from pomodoro.core.auth import hash_password, hash_session_token
from pomodoro.core.rate_limit import MAX_FAILED_ATTEMPTS, WINDOW, RateLimiter
from pomodoro.database.auth_session_repository import SqlAuthSessionRepository
from pomodoro.database.tables import SQLModel
from pomodoro.database.user_repository import SqlUserRepository
from pomodoro.entrypoints.app import create_app
from pomodoro.entrypoints.dependencies import get_engine, require_session

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine

    from pomodoro.core.entities import AuthSession, UserId

pytestmark = pytest.mark.unit

_VALID_PASSWORD = "correct horse battery staple"
_IP = "1.2.3.4"
_EMAIL_KEY = "a@example.com"


def _record_failures(limiter: RateLimiter, *, count: int, now: datetime) -> None:
    for _ in range(count):
        limiter.record_failure(ip=_IP, email_key=_EMAIL_KEY, now=now)


class TestRateLimiter:
    def test_allows_attempts_under_the_threshold(self) -> None:
        limiter = RateLimiter()
        now = datetime.now(UTC)
        _record_failures(limiter, count=MAX_FAILED_ATTEMPTS - 1, now=now)

        assert limiter.is_blocked(ip=_IP, email_key=_EMAIL_KEY, now=now) is False

    def test_blocks_once_the_threshold_is_reached(self) -> None:
        limiter = RateLimiter()
        now = datetime.now(UTC)
        _record_failures(limiter, count=MAX_FAILED_ATTEMPTS, now=now)

        assert limiter.is_blocked(ip=_IP, email_key=_EMAIL_KEY, now=now) is True

    def test_does_not_block_a_different_ip_or_email(self) -> None:
        limiter = RateLimiter()
        now = datetime.now(UTC)
        _record_failures(limiter, count=MAX_FAILED_ATTEMPTS, now=now)

        assert limiter.is_blocked(ip="5.6.7.8", email_key=_EMAIL_KEY, now=now) is False
        assert limiter.is_blocked(ip=_IP, email_key="b@example.com", now=now) is False

    def test_unblocks_once_the_window_has_passed(self) -> None:
        limiter = RateLimiter()
        now = datetime.now(UTC)
        _record_failures(limiter, count=MAX_FAILED_ATTEMPTS, now=now)

        later = now + WINDOW + timedelta(seconds=1)

        assert limiter.is_blocked(ip=_IP, email_key=_EMAIL_KEY, now=later) is False

    def test_reset_clears_recorded_failures(self) -> None:
        limiter = RateLimiter()
        now = datetime.now(UTC)
        _record_failures(limiter, count=MAX_FAILED_ATTEMPTS, now=now)

        limiter.reset(ip=_IP, email_key=_EMAIL_KEY)

        assert limiter.is_blocked(ip=_IP, email_key=_EMAIL_KEY, now=now) is False

    def test_storage_evicts_expired_entries_instead_of_growing_unbounded(self) -> None:
        limiter = RateLimiter()
        now = datetime.now(UTC)
        for i in range(50):
            limiter.record_failure(ip=f"10.0.0.{i}", email_key=_EMAIL_KEY, now=now)
        assert len(limiter._attempts) == 50

        later = now + WINDOW + timedelta(seconds=1)
        limiter.record_failure(ip="9.9.9.9", email_key="new@example.com", now=later)

        assert len(limiter._attempts) == 1


class TestEnforceLoginRateLimit:
    def test_raises_429_once_blocked(self) -> None:
        limiter = RateLimiter()
        now = datetime.now(UTC)
        _record_failures(limiter, count=MAX_FAILED_ATTEMPTS, now=now)

        with pytest.raises(HTTPException) as exc_info:
            enforce_login_rate_limit(limiter, ip=_IP, email_key=_EMAIL_KEY, now=now)
        assert exc_info.value.status_code == 429

    def test_does_not_raise_under_the_threshold(self) -> None:
        limiter = RateLimiter()
        now = datetime.now(UTC)

        enforce_login_rate_limit(limiter, ip=_IP, email_key=_EMAIL_KEY, now=now)


def _csrf_guarded_app() -> FastAPI:
    app = FastAPI()
    router = APIRouter()

    @router.post("/_throwaway-mutate")
    def _mutate(_: None = Depends(require_json_content_type)) -> bool:
        return True

    @router.get("/_throwaway-read")
    def _read(_: None = Depends(require_json_content_type)) -> bool:
        return True

    app.include_router(router)
    return app


class TestRequireJsonContentType:
    def test_get_requests_are_never_guarded(self) -> None:
        client = TestClient(_csrf_guarded_app())

        response = client.get("/_throwaway-read")

        assert response.status_code == 200

    def test_post_with_json_content_type_is_allowed(self) -> None:
        client = TestClient(_csrf_guarded_app())

        response = client.post("/_throwaway-mutate", json={})

        assert response.status_code == 200

    def test_post_with_a_non_json_content_type_is_rejected(self) -> None:
        client = TestClient(_csrf_guarded_app())

        response = client.post(
            "/_throwaway-mutate",
            data="field=value",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 403

    def test_post_with_no_body_is_rejected(self) -> None:
        client = TestClient(_csrf_guarded_app())

        response = client.post("/_throwaway-mutate")

        assert response.status_code == 403


def _ip_app() -> FastAPI:
    app = FastAPI()
    router = APIRouter()

    @router.get("/_throwaway-ip")
    def _ip(request: Request, trust: bool = False) -> str:
        return resolve_client_ip(request, trust_forwarded_for=trust)

    app.include_router(router)
    return app


class TestResolveClientIp:
    def test_ignores_x_forwarded_for_by_default(self) -> None:
        client = TestClient(_ip_app())

        response = client.get("/_throwaway-ip", headers={"x-forwarded-for": "203.0.113.5"})

        assert response.json() != "203.0.113.5"

    def test_ignores_x_forwarded_for_when_trust_is_explicitly_disabled(self) -> None:
        client = TestClient(_ip_app())

        response = client.get(
            "/_throwaway-ip",
            headers={"x-forwarded-for": "203.0.113.5"},
            params={"trust": "false"},
        )

        assert response.json() != "203.0.113.5"

    def test_trusts_the_first_forwarded_ip_once_explicitly_enabled(self) -> None:
        client = TestClient(_ip_app())

        response = client.get(
            "/_throwaway-ip",
            headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1"},
            params={"trust": "true"},
        )

        assert response.json() == "203.0.113.5"


def _session_guarded_app() -> FastAPI:
    app = create_app()
    router = APIRouter()

    @router.get("/api/v1/_throwaway-session")
    def _whoami(auth_session: AuthSession = Depends(require_session)) -> int:
        return auth_session.user_id

    app.include_router(router)
    return app


def _create_user(session: Session, *, email: str = "a@example.com") -> UserId:
    user = SqlUserRepository(session).add(
        email=email,
        password_hash=hash_password(_VALID_PASSWORD),
        time_zone="UTC",
        created_at=datetime.now(UTC),
    )
    return user.id


def _create_auth_session(
    session: Session,
    *,
    user_id: UserId,
    token: str,
    last_used_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> AuthSession:
    now = datetime.now(UTC)
    return SqlAuthSessionRepository(session).add(
        user_id=user_id,
        token_hash=hash_session_token(token),
        created_at=now,
        last_used_at=last_used_at or now,
        expires_at=expires_at or now + timedelta(days=30),
    )


class TestRequireSession:
    @pytest.fixture(autouse=True)
    def engine(self, _in_memory_database: None) -> Engine:
        # Explicitly depend on the conftest autouse fixture so it runs first: it sets
        # DATABASE_URL and clears the cached engine, and fixture ordering between a
        # conftest-level and a class-level autouse fixture is otherwise unspecified.
        db_engine = get_engine()
        SQLModel.metadata.create_all(db_engine)
        return db_engine

    @pytest.fixture
    def session(self, engine: Engine) -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    def test_missing_cookie_is_rejected(self) -> None:
        client = TestClient(_session_guarded_app())

        response = client.get("/api/v1/_throwaway-session")

        assert response.status_code == 401

    def test_unknown_token_is_rejected(self) -> None:
        client = TestClient(_session_guarded_app())
        client.cookies.set(SESSION_COOKIE_NAME, "not-a-real-token")

        response = client.get("/api/v1/_throwaway-session")

        assert response.status_code == 401

    def test_expired_session_is_rejected(self, session: Session) -> None:
        user_id = _create_user(session)
        now = datetime.now(UTC)
        _create_auth_session(
            session,
            user_id=user_id,
            token="expired-token",
            last_used_at=now - timedelta(days=31),
            expires_at=now - timedelta(seconds=1),
        )
        client = TestClient(_session_guarded_app())
        client.cookies.set(SESSION_COOKIE_NAME, "expired-token")

        response = client.get("/api/v1/_throwaway-session")

        assert response.status_code == 401

    def test_revoked_session_is_rejected(self, session: Session) -> None:
        user_id = _create_user(session)
        created = _create_auth_session(session, user_id=user_id, token="revoked-token")
        SqlAuthSessionRepository(session).delete(created.id)
        client = TestClient(_session_guarded_app())
        client.cookies.set(SESSION_COOKIE_NAME, "revoked-token")

        response = client.get("/api/v1/_throwaway-session")

        assert response.status_code == 401

    def test_valid_session_resolves_to_its_user(self, session: Session) -> None:
        user_id = _create_user(session)
        _create_auth_session(session, user_id=user_id, token="good-token")
        client = TestClient(_session_guarded_app())
        client.cookies.set(SESSION_COOKIE_NAME, "good-token")

        response = client.get("/api/v1/_throwaway-session")

        assert response.status_code == 200
        assert response.json() == user_id

    def test_sliding_renewal_extends_expiry_past_the_threshold(self, session: Session) -> None:
        user_id = _create_user(session)
        now = datetime.now(UTC)
        stale_last_used = now - SESSION_RENEWAL_THRESHOLD - timedelta(minutes=1)
        created = _create_auth_session(
            session,
            user_id=user_id,
            token="stale-token",
            last_used_at=stale_last_used,
            expires_at=stale_last_used + timedelta(days=30),
        )
        client = TestClient(_session_guarded_app())
        client.cookies.set(SESSION_COOKIE_NAME, "stale-token")

        response = client.get("/api/v1/_throwaway-session")

        assert response.status_code == 200
        assert "set-cookie" in response.headers
        refetched = SqlAuthSessionRepository(session).get_by_token_hash(
            hash_session_token("stale-token")
        )
        assert refetched is not None
        assert refetched.last_used_at > created.last_used_at
        assert refetched.expires_at > created.expires_at

    def test_renewal_is_skipped_under_the_threshold(self, session: Session) -> None:
        user_id = _create_user(session)
        _create_auth_session(session, user_id=user_id, token="fresh-token")
        client = TestClient(_session_guarded_app())
        client.cookies.set(SESSION_COOKIE_NAME, "fresh-token")

        response = client.get("/api/v1/_throwaway-session")

        assert response.status_code == 200
        assert "set-cookie" not in response.headers
