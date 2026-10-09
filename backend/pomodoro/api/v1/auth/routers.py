"""CES-17 · POST /api/v1/auth/register (User Stories 1-5).

FastAPI resolves every dependency callable's full signature (including `Depends`-typed
parameters and return types) via `typing.get_type_hints` when the app is built. With
`from __future__ import annotations`, that means every name in this module's annotations must
be a real, module-level import — moving one behind `if TYPE_CHECKING:` raises `NameError` at
startup. See the `TC001`/`TC002`/`TC003` per-file-ignore for this path in `pyproject.toml`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from pomodoro.api.v1.auth.schemas.requests.register import RegisterRequest
from pomodoro.api.v1.auth.schemas.responses.session import UserResponse
from pomodoro.api.v1.auth.use_cases import register_user
from pomodoro.core.auth_sessions import SESSION_DURATION, AuthSessionRepository
from pomodoro.core.clock import Clock, get_clock
from pomodoro.core.users import UserRepository
from pomodoro.database.repositories.auth_session import get_auth_session_repository
from pomodoro.database.repositories.user import get_user_repository

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE_NAME = "session"


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
    response: Response,
    clock: Clock = Depends(get_clock),
    user_repository: UserRepository = Depends(get_user_repository),
    auth_session_repository: AuthSessionRepository = Depends(get_auth_session_repository),
) -> UserResponse:
    """Create a User, auto-log them in, and set the session cookie."""
    registered = register_user(
        email=payload.email,
        password=payload.password,
        time_zone=payload.time_zone,
        clock=clock,
        user_repository=user_repository,
        auth_session_repository=auth_session_repository,
    )
    _set_session_cookie(response, registered.raw_token)
    return UserResponse(
        id=registered.user.id,
        email=registered.user.email,
        time_zone=registered.user.time_zone,
        alarm_enabled=registered.user.alarm_enabled,
        notifications_enabled=registered.user.notifications_enabled,
        created_at=registered.user.created_at,
    )
