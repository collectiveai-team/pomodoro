"""Auth endpoints: register, login, logout, me, change-password, delete-account.

Per the house convention (api/<area> owns router + schemas + use case), the
orchestration lives here; `pomodoro.core.auth` supplies the framework-free
rules (hashing, validation) and `pomodoro.api.session` supplies the cookie
lifecycle every endpoint here also relies on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from pomodoro.api.session import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    get_auth_session_repository,
    get_clock,
    get_user_repository,
    require_session,
    start_session,
)
from pomodoro.core.auth import (
    hash_password,
    hash_session_token,
    validate_email_format,
    validate_password_length,
    validate_time_zone,
    verify_password,
)
from pomodoro.core.clock import Clock
from pomodoro.core.entities import AuthSessionId, User, UserId
from pomodoro.core.errors import (
    EmailAlreadyRegisteredError,
    IncorrectPasswordError,
    InvalidEmailError,
    InvalidPasswordLengthError,
    InvalidTimeZoneError,
)
from pomodoro.core.normalization import normalize_key
from pomodoro.core.repositories import AuthSessionRepository, UserRepository

router = APIRouter(prefix="/api/auth", tags=["auth"])

UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]
SessionRepoDep = Annotated[AuthSessionRepository, Depends(get_auth_session_repository)]
ClockDep = Annotated[Clock, Depends(get_clock)]

GENERIC_LOGIN_ERROR = "email o contraseña incorrectos"
RATE_LIMIT_ERROR = "Demasiados intentos. Probá de nuevo más tarde."

DEFAULT_MAX_FAILED_ATTEMPTS = 5
DEFAULT_RATE_LIMIT_WINDOW = timedelta(minutes=15)


@dataclass
class RateLimiter:
    """Sliding-window failed-attempt counter, keyed by a caller-chosen string.

    An in-memory, single-process counter is an acceptable v1 implementation
    per the spec; a multi-instance deployment would need a shared store
    (e.g. Redis) instead of this per-process dict.
    """

    max_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS
    window: timedelta = DEFAULT_RATE_LIMIT_WINDOW
    _attempts: dict[str, list[datetime]] = field(default_factory=dict)

    def is_blocked(self, key: str, now: datetime) -> bool:
        """Return whether `key` has reached `max_attempts` failures within `window`."""
        return len(self._recent(key, now)) >= self.max_attempts

    def record_failure(self, key: str, now: datetime) -> None:
        """Record a failed attempt for `key` at `now`."""
        self._attempts[key] = [*self._recent(key, now), now]

    def _recent(self, key: str, now: datetime) -> list[datetime]:
        cutoff = now - self.window
        return [timestamp for timestamp in self._attempts.get(key, []) if timestamp > cutoff]


def get_login_rate_limiter() -> RateLimiter:
    """Stand in for the login RateLimiter dependency until the app factory overrides it."""
    raise NotImplementedError("RateLimiter dependency must be wired by the app factory")


def get_register_rate_limiter() -> RateLimiter:
    """Stand in for the register RateLimiter dependency until the app factory overrides it."""
    raise NotImplementedError("RateLimiter dependency must be wired by the app factory")


class RegisterRequest(BaseModel):
    """Request body for `POST /api/auth/register`."""

    email: str
    password: str
    time_zone: str


class LoginRequest(BaseModel):
    """Request body for `POST /api/auth/login`."""

    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    """Request body for `POST /api/auth/change-password`."""

    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    """Request body for `POST /api/auth/delete-account`."""

    password: str


class UserPublic(BaseModel):
    """The User's public fields: never a password hash or any `*_key` column."""

    id: int
    email: str
    time_zone: str
    alarm_enabled: bool
    notifications_enabled: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> UserPublic:
        """Build the public response shape from a `core` `User` entity."""
        return cls(
            id=user.id,
            email=user.email,
            time_zone=user.time_zone,
            alarm_enabled=user.alarm_enabled,
            notifications_enabled=user.notifications_enabled,
            created_at=user.created_at,
        )


def _rate_limit_key(request: Request, email: str) -> str:
    host = request.client.host if request.client is not None else "unknown"
    return f"{host}:{normalize_key(email)}"


def _enforce_rate_limit(limiter: RateLimiter, key: str, now: datetime) -> None:
    if limiter.is_blocked(key, now):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, RATE_LIMIT_ERROR)


def _current_session_id(
    request: Request, session_repo: AuthSessionRepository
) -> AuthSessionId | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        return None
    auth_session = session_repo.get_by_token_hash(hash_session_token(token))
    return auth_session.id if auth_session is not None else None


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    user_repo: UserRepoDep,
    session_repo: SessionRepoDep,
    clock: ClockDep,
    limiter: Annotated[RateLimiter, Depends(get_register_rate_limiter)],
) -> UserPublic:
    """Create the User, store the browser-detected `time_zone`, and log them in."""
    now = clock.now()
    key = _rate_limit_key(request, body.email)
    _enforce_rate_limit(limiter, key, now)

    try:
        normalized_email = validate_email_format(body.email)
        validate_password_length(body.password)
        validate_time_zone(body.time_zone)
    except (InvalidEmailError, InvalidPasswordLengthError, InvalidTimeZoneError) as error:
        limiter.record_failure(key, now)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    email_key = normalize_key(normalized_email)
    if user_repo.get_by_email_key(email_key) is not None:
        limiter.record_failure(key, now)
        error = EmailAlreadyRegisteredError()
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    user = User(
        id=UserId(0),
        email=normalized_email,
        email_key=email_key,
        created_at=now,
        time_zone=body.time_zone,
        alarm_enabled=True,
        notifications_enabled=True,
    )
    try:
        stored = user_repo.add(user, password_hash=hash_password(body.password))
    except EmailAlreadyRegisteredError as error:
        # Lost a race against a concurrent registration of the same email
        # that passed the pre-check above first; same response as that check.
        limiter.record_failure(key, now)
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    start_session(response, stored.id, session_repo=session_repo, clock=clock)
    return UserPublic.from_entity(stored)


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    user_repo: UserRepoDep,
    session_repo: SessionRepoDep,
    clock: ClockDep,
    limiter: Annotated[RateLimiter, Depends(get_login_rate_limiter)],
) -> UserPublic:
    """Log the User in, responding with a generic message on any failure."""
    now = clock.now()
    key = _rate_limit_key(request, body.email)
    _enforce_rate_limit(limiter, key, now)

    record = user_repo.get_by_email_key(normalize_key(body.email))
    if record is None or not verify_password(body.password, record.password_hash):
        limiter.record_failure(key, now)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)

    start_session(response, record.user.id, session_repo=session_repo, clock=clock)
    return UserPublic.from_entity(record.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    _user: Annotated[User, Depends(require_session)],
    session_repo: SessionRepoDep,
) -> None:
    """Revoke only the session carried by the caller's cookie."""
    session_id = _current_session_id(request, session_repo)
    if session_id is not None:
        session_repo.revoke(session_id)
    clear_session_cookie(response)


@router.get("/me")
def me(user: Annotated[User, Depends(require_session)]) -> UserPublic:
    """Return the current User's public fields only."""
    return UserPublic.from_entity(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: Annotated[User, Depends(require_session)],
    user_repo: UserRepoDep,
    session_repo: SessionRepoDep,
) -> None:
    """Change the password after confirming the current one, keeping only this session."""
    record = user_repo.get_by_email_key(user.email_key)
    if record is None or not verify_password(body.current_password, record.password_hash):
        error = IncorrectPasswordError()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    try:
        validate_password_length(body.new_password)
    except InvalidPasswordLengthError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    user_repo.update_password_hash(user.id, hash_password(body.new_password))

    session_id = _current_session_id(request, session_repo)
    if session_id is not None:
        session_repo.revoke_all_for_user_except(user.id, session_id)


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: DeleteAccountRequest,
    response: Response,
    user: Annotated[User, Depends(require_session)],
    user_repo: UserRepoDep,
) -> None:
    """Confirm the password, then permanently delete the User and all of their data."""
    record = user_repo.get_by_email_key(user.email_key)
    if record is None or not verify_password(body.password, record.password_hash):
        error = IncorrectPasswordError()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    user_repo.delete(user.id)
    clear_session_cookie(response)
