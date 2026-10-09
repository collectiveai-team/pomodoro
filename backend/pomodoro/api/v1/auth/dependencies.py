"""CES-17 · The session guard: one dependency every protected route relies on.

`get_current_user` (and `get_current_session`, for routes that only need the session itself,
such as logout) is the single seam that turns a request's cookie into a 401 or an authenticated
caller — centralizing cookie parsing, hashing, expiry, and sliding renewal here means no router
re-implements any part of it.

Same FastAPI type-hint-resolution caveat as `routers.py`: every annotated name must be a real,
module-level import, never `TYPE_CHECKING`-only.
"""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request

from pomodoro.api.v1.auth.rate_limit import RateLimiter
from pomodoro.core.auth_sessions import (
    SESSION_COOKIE_NAME,
    AuthSession,
    AuthSessionRepository,
    hash_session_token,
    needs_renewal,
)
from pomodoro.core.clock import Clock, get_clock
from pomodoro.core.users import User, UserRepository
from pomodoro.database.repositories.auth_session import get_auth_session_repository
from pomodoro.database.repositories.user import get_user_repository


def get_current_session(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    clock: Clock = Depends(get_clock),
    auth_session_repository: AuthSessionRepository = Depends(get_auth_session_repository),
) -> AuthSession:
    """Resolve the caller's `AuthSession` from the session cookie, or raise 401.

    A missing cookie, an unknown token, or one whose `expires_at` has passed are all
    indistinguishable 401s. A session due for its sliding renewal (`needs_renewal`) is touched
    here, so every authenticated request organically keeps a live session alive.
    """
    if session is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    now = clock.now()
    auth_session = auth_session_repository.get_by_token_hash(hash_session_token(session))
    if auth_session is None or auth_session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    if needs_renewal(auth_session, now):
        auth_session_repository.touch(auth_session.id, now)

    return auth_session


def get_current_user(
    auth_session: AuthSession = Depends(get_current_session),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    """Resolve the caller's `User` from their validated session, or raise 401."""
    user = user_repository.get_by_id(auth_session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user


def get_rate_limiter(request: Request) -> RateLimiter:
    """Dependency provider: the per-app `RateLimiter` set on `app.state` by `create_app()`."""
    return request.app.state.rate_limiter
