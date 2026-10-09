"""Auth endpoints: register, login, logout, me, change-password, delete-account (T9).

Thin handlers: validation and persistence delegate to `core.auth`/`core.time_zone`
and the T7 repositories, and the cookie/CSRF/rate-limit helpers are the shared T8
primitives from `api.v1.session`. State this module needs but may not build
itself (the database session, the rate limiter, the resolved `AuthSession`, and
`Settings.trust_forwarded_for`) comes through the typed placeholders in
`api.v1.dependencies`, overridden with their real `entrypoints.dependencies`
implementations by `entrypoints.app.create_app()` (CES-5: `api` may never import
`entrypoints`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session

from pomodoro.api.v1 import dependencies as deps
from pomodoro.api.v1.schemas.requests.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
)
from pomodoro.api.v1.schemas.responses.auth import UserResponse
from pomodoro.api.v1.session import (
    SESSION_TTL,
    clear_session_cookie,
    enforce_login_rate_limit,
    require_json_content_type,
    resolve_client_ip,
    set_session_cookie,
)
from pomodoro.core.auth import (
    email_key,
    generate_session_token,
    hash_password,
    hash_session_token,
    normalize_email,
    verify_password,
)
from pomodoro.core.errors import DomainError
from pomodoro.core.time_zone import validate_time_zone
from pomodoro.database.account_deletion import delete_user_account
from pomodoro.database.auth_session_repository import SqlAuthSessionRepository
from pomodoro.database.user_repository import SqlUserRepository

if TYPE_CHECKING:
    from pomodoro.core.entities import AuthSession, User, UserId
    from pomodoro.core.rate_limit import RateLimiter

# Spec story 6: the same generic message for both an unknown email and a wrong
# password, so a login attempt never discloses whether an email is registered.
_INVALID_CREDENTIALS = "email o contraseña incorrectos"

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(require_json_content_type)])


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        time_zone=user.time_zone,
        alarm_enabled=user.alarm_enabled,
        notifications_enabled=user.notifications_enabled,
    )


def _issue_session(
    db_session: Session, response: Response, *, user_id: UserId, now: datetime
) -> None:
    token = generate_session_token()
    SqlAuthSessionRepository(db_session).add(
        user_id=user_id,
        token_hash=hash_session_token(token),
        created_at=now,
        last_used_at=now,
        expires_at=now + SESSION_TTL,
    )
    set_session_cookie(response, token=token)


def _invalid_credentials() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db_session: Session = Depends(deps.get_db_session),
    limiter: RateLimiter = Depends(deps.get_rate_limiter),
    trust_forwarded_for: bool = Depends(deps.get_trust_forwarded_for),
) -> UserResponse:
    """Register a new User, validating email/password/time_zone, then log them in."""
    ip = resolve_client_ip(request, trust_forwarded_for=trust_forwarded_for)
    now = datetime.now(UTC)
    key = email_key(payload.email)
    enforce_login_rate_limit(limiter, ip=ip, email_key=key, now=now)

    try:
        normalized_email = normalize_email(payload.email)
        validate_time_zone(payload.time_zone)
        password_hash = hash_password(payload.password)
        user = SqlUserRepository(db_session).add(
            email=normalized_email,
            password_hash=password_hash,
            time_zone=payload.time_zone,
            created_at=now,
        )
    except DomainError:
        limiter.record_failure(ip=ip, email_key=key, now=now)
        raise
    limiter.reset(ip=ip, email_key=key)

    _issue_session(db_session, response, user_id=user.id, now=now)
    return _to_user_response(user)


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db_session: Session = Depends(deps.get_db_session),
    limiter: RateLimiter = Depends(deps.get_rate_limiter),
    trust_forwarded_for: bool = Depends(deps.get_trust_forwarded_for),
) -> UserResponse:
    """Log an existing User in, rejecting unknown email and wrong password identically."""
    ip = resolve_client_ip(request, trust_forwarded_for=trust_forwarded_for)
    now = datetime.now(UTC)
    key = email_key(payload.email)
    enforce_login_rate_limit(limiter, ip=ip, email_key=key, now=now)

    user_repo = SqlUserRepository(db_session)
    user = user_repo.get_by_email(payload.email)
    stored_hash = user_repo.get_password_hash(user.id) if user is not None else None
    if user is None or stored_hash is None or not verify_password(payload.password, stored_hash):
        limiter.record_failure(ip=ip, email_key=key, now=now)
        raise _invalid_credentials()
    limiter.reset(ip=ip, email_key=key)

    _issue_session(db_session, response, user_id=user.id, now=now)
    return _to_user_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> None:
    """Revoke only the current session."""
    SqlAuthSessionRepository(db_session).delete(auth_session.id)
    clear_session_cookie(response)


@router.get("/me")
def me(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> UserResponse:
    """Return the authenticated User."""
    user = SqlUserRepository(db_session).get_by_id(auth_session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return _to_user_response(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> None:
    """Replace the User's password, requiring the current one, and revoke every other session."""
    user_repo = SqlUserRepository(db_session)
    current_hash = user_repo.get_password_hash(auth_session.user_id)
    if current_hash is None or not verify_password(payload.current_password, current_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect."
        )
    user_repo.update_password_hash(auth_session.user_id, hash_password(payload.new_password))
    SqlAuthSessionRepository(db_session).delete_all_for_user_except(
        auth_session.user_id, keep_session_id=auth_session.id
    )


@router.post("/delete-account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: DeleteAccountRequest,
    response: Response,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> None:
    """Permanently delete the User's account and every row depending on it."""
    current_hash = SqlUserRepository(db_session).get_password_hash(auth_session.user_id)
    if current_hash is None or not verify_password(payload.password, current_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect."
        )
    delete_user_account(db_session, auth_session.user_id)
    clear_session_cookie(response)
