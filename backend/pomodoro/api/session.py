"""Session-cookie lifecycle, the `require_session` dependency, and the CSRF guard.

The app factory overrides `get_clock`/`get_user_repository`/
`get_auth_session_repository` with real implementations; every non-auth router
built on later tickets depends on `require_session` for its authenticated User.
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from pomodoro.core.auth import generate_session_token, hash_session_token
from pomodoro.core.clock import Clock
from pomodoro.core.entities import User, UserId
from pomodoro.core.repositories import AuthSessionRepository, UserRepository

SESSION_COOKIE_NAME = "session_token"
SESSION_TTL = timedelta(days=30)

# Sliding-expiry renewal granularity: touching the database on every request would
# turn every read into a write. An hour of slack means a User active at least once
# an hour never sees their session lapse early, while idle sessions still expire
# on schedule.
SESSION_RENEWAL_THRESHOLD = timedelta(hours=1)

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_clock() -> Clock:
    """Stand in for the Clock dependency until the app factory overrides it."""
    raise NotImplementedError("Clock dependency must be wired by the app factory")


def get_user_repository() -> UserRepository:
    """Stand in for the UserRepository dependency until the app factory overrides it."""
    raise NotImplementedError("UserRepository dependency must be wired by the app factory")


def get_auth_session_repository() -> AuthSessionRepository:
    """Stand in for the AuthSessionRepository dependency until the app factory overrides it."""
    raise NotImplementedError("AuthSessionRepository dependency must be wired by the app factory")


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the session cookie to `response` with the required attributes."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    """Remove the session cookie from the caller's browser."""
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def start_session(
    response: Response,
    user_id: UserId,
    *,
    session_repo: AuthSessionRepository,
    clock: Clock,
) -> str:
    """Create a new AuthSession for `user_id` and set its cookie on `response`.

    Returns the raw (unhashed) token; only its hash is ever persisted.
    """
    token = generate_session_token()
    session_repo.create(
        user_id, token_hash=hash_session_token(token), expires_at=clock.now() + SESSION_TTL
    )
    set_session_cookie(response, token)
    return token


def require_session(
    request: Request,
    session_repo: Annotated[AuthSessionRepository, Depends(get_auth_session_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> User:
    """Resolve the current User from the session cookie, or respond 401.

    Renews the sliding expiry when `last_used_at` is older than
    `SESSION_RENEWAL_THRESHOLD`, so a merely-active User isn't written to the
    database on every single request.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "no session cookie")

    auth_session = session_repo.get_by_token_hash(hash_session_token(token))
    if auth_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")

    now = clock.now()
    if auth_session.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")

    user = user_repo.get_by_id(auth_session.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")

    if now - auth_session.last_used_at >= SESSION_RENEWAL_THRESHOLD:
        session_repo.touch_last_used(auth_session.id, expires_at=now + SESSION_TTL)

    return user


async def csrf_guard(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Reject mutating requests that don't carry `Content-Type: application/json`.

    Combined with the cookie's `SameSite=Lax`, this blocks a cross-site HTML
    form submission from ever reaching a mutating route: a plain HTML form
    cannot set an arbitrary `Content-Type` header.
    """
    if request.method in _MUTATING_METHODS:
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            body = {"detail": "Content-Type must be application/json"}
            return JSONResponse(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, content=body)
    return await call_next(request)
