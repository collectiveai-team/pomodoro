"""CES-17 · POST /api/v1/auth/register (User Stories 1-5).

FastAPI resolves every dependency callable's full signature (including `Depends`-typed
parameters and return types) via `typing.get_type_hints` when the app is built. With
`from __future__ import annotations`, that means every name in this module's annotations must
be a real, module-level import — moving one behind `if TYPE_CHECKING:` raises `NameError` at
startup. See the `TC001`/`TC002`/`TC003` per-file-ignore for this path in `pyproject.toml`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from pomodoro.api.v1.auth.dependencies import (
    get_current_session,
    get_current_user,
    get_rate_limiter,
)
from pomodoro.api.v1.auth.rate_limit import RateLimiter, rate_limit_key
from pomodoro.api.v1.auth.schemas.requests.login import LoginRequest
from pomodoro.api.v1.auth.schemas.requests.register import RegisterRequest
from pomodoro.api.v1.auth.schemas.responses.session import UserResponse
from pomodoro.api.v1.auth.use_cases import login_user, register_user
from pomodoro.core.auth_sessions import (
    SESSION_COOKIE_NAME,
    SESSION_DURATION,
    AuthSession,
    AuthSessionRepository,
)
from pomodoro.core.clock import Clock, get_clock
from pomodoro.core.users import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidEmailError,
    InvalidPasswordLengthError,
    User,
    UserRepository,
)
from pomodoro.database.repositories.auth_session import get_auth_session_repository
from pomodoro.database.repositories.user import get_user_repository

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        time_zone=user.time_zone,
        alarm_enabled=user.alarm_enabled,
        notifications_enabled=user.notifications_enabled,
        created_at=user.created_at,
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=int(SESSION_DURATION.total_seconds()),
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.post("/register", status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    clock: Clock = Depends(get_clock),
    user_repository: UserRepository = Depends(get_user_repository),
    auth_session_repository: AuthSessionRepository = Depends(get_auth_session_repository),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> UserResponse:
    """Create a User, auto-log them in, and set the session cookie.

    Throttled by IP + email (User Story 12): a failed attempt counts against the limiter, a
    successful one does not.
    """
    now = clock.now()
    key = rate_limit_key(_client_ip(request), payload.email)
    rate_limiter.check(key, now)
    try:
        registered = register_user(
            email=payload.email,
            password=payload.password,
            time_zone=payload.time_zone,
            clock=clock,
            user_repository=user_repository,
            auth_session_repository=auth_session_repository,
        )
    except InvalidEmailError, DuplicateEmailError, InvalidPasswordLengthError:
        rate_limiter.record_failure(key, now)
        raise
    _set_session_cookie(response, registered.raw_token)
    return _user_response(registered.user)


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    clock: Clock = Depends(get_clock),
    user_repository: UserRepository = Depends(get_user_repository),
    auth_session_repository: AuthSessionRepository = Depends(get_auth_session_repository),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> UserResponse:
    """Verify credentials and log the User in with a fresh session.

    Throttled by IP + email (User Story 12): a failed attempt counts against the limiter, a
    successful one does not.
    """
    now = clock.now()
    key = rate_limit_key(_client_ip(request), payload.email)
    rate_limiter.check(key, now)
    try:
        authenticated = login_user(
            email=payload.email,
            password=payload.password,
            clock=clock,
            user_repository=user_repository,
            auth_session_repository=auth_session_repository,
        )
    except InvalidCredentialsError:
        rate_limiter.record_failure(key, now)
        raise
    _set_session_cookie(response, authenticated.raw_token)
    return _user_response(authenticated.user)


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> UserResponse:
    """Return the caller's own public profile."""
    return _user_response(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    auth_session: AuthSession = Depends(get_current_session),
    auth_session_repository: AuthSessionRepository = Depends(get_auth_session_repository),
) -> None:
    """Revoke the caller's current session and clear its cookie."""
    auth_session_repository.revoke(auth_session.id)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
