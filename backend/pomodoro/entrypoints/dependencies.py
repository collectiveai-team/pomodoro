"""Real FastAPI dependency providers, wired in the app factory (never stubs)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, Request, Response, status
from sqlmodel import Session

from pomodoro.api.v1.session import (
    SESSION_COOKIE_NAME,
    SESSION_RENEWAL_THRESHOLD,
    SESSION_TTL,
    set_session_cookie,
)
from pomodoro.core.auth import hash_session_token
from pomodoro.core.rate_limit import RateLimiter
from pomodoro.database.auth_session_repository import SqlAuthSessionRepository
from pomodoro.database.engine import build_engine
from pomodoro.entrypoints.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.engine import Engine

    from pomodoro.core.entities import AuthSession


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide engine, built once from the configured database URL."""
    return build_engine(get_settings().database_url)


def get_db_session() -> Iterator[Session]:
    """Yield a SQLModel session bound to the configured engine, closing it after the request."""
    with Session(get_engine()) as session:
        yield session


@lru_cache
def get_rate_limiter() -> RateLimiter:
    """Return the process-wide login/register rate limiter (T8), shared across requests."""
    return RateLimiter()


def get_trust_forwarded_for() -> bool:
    """Expose `Settings.trust_forwarded_for` to `api` routers without an upward import (T9)."""
    return get_settings().trust_forwarded_for


def require_session(
    request: Request,
    response: Response,
    db_session: Session = Depends(get_db_session),
) -> AuthSession:
    """Resolve the caller's `AuthSession` from its cookie, or 401 (issue #12 spec).

    Renews the sliding 30-day expiry only once `SESSION_RENEWAL_THRESHOLD` has
    passed since `last_used_at`, so an active User's session stays alive
    without a database write on every single request.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise _unauthenticated()

    repo = SqlAuthSessionRepository(db_session)
    auth_session = repo.get_by_token_hash(hash_session_token(token))
    now = datetime.now(UTC)
    if auth_session is None or auth_session.expires_at <= now:
        raise _unauthenticated()

    if now - auth_session.last_used_at >= SESSION_RENEWAL_THRESHOLD:
        auth_session = repo.update(
            replace(auth_session, last_used_at=now, expires_at=now + SESSION_TTL)
        )
        set_session_cookie(response, token=token)

    return auth_session


def _unauthenticated() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
