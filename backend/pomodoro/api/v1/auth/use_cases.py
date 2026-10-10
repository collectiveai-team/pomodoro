"""Register and login use cases: the orchestration `routers.py` delegates to."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from pomodoro.core.auth_sessions import (
    AuthSession,
    AuthSessionId,
    AuthSessionRepository,
    generate_session_token,
    hash_session_token,
    issue_session,
)
from pomodoro.core.logger import get_logger
from pomodoro.core.passwords import hash_password, verify_password
from pomodoro.core.users import (
    DuplicateEmailError,
    InvalidCredentialsError,
    User,
    UserId,
    UserRepository,
    normalize_email,
    validate_email_format,
    validate_password_length,
)

if TYPE_CHECKING:
    from pomodoro.core.clock import Clock

log = get_logger(__name__)

_INVALID_CREDENTIALS_MESSAGE = "Email o contraseña incorrectos."


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """What a successful register or login produces.

    The raw token exists only here, long enough for the router to set it as a cookie — it is
    never stored (only `session.token_hash` is).
    """

    user: User
    session: AuthSession
    raw_token: str


def register_user(
    *,
    email: str,
    password: str,
    time_zone: str,
    clock: Clock,
    user_repository: UserRepository,
    auth_session_repository: AuthSessionRepository,
) -> AuthenticatedSession:
    """Validate, create the User, and auto-log them in with a fresh session."""
    validate_email_format(email)
    email_key = normalize_email(email)
    if user_repository.get_by_email_key(email_key) is not None:
        raise DuplicateEmailError(f"'{email}' is already registered.")
    validate_password_length(password)

    now = clock.now()
    user = User(
        id=UserId(uuid4()),
        email=email.strip(),
        email_key=email_key,
        time_zone=time_zone,
        alarm_enabled=True,
        notifications_enabled=False,
        created_at=now,
    )
    user_repository.add(user, hash_password(password))

    raw_token = generate_session_token()
    session = issue_session(
        session_id=AuthSessionId(uuid4()),
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        now=now,
    )
    auth_session_repository.add(session)

    log.info("user_registered", user_id=str(user.id))
    return AuthenticatedSession(user=user, session=session, raw_token=raw_token)


def login_user(
    *,
    email: str,
    password: str,
    clock: Clock,
    user_repository: UserRepository,
    auth_session_repository: AuthSessionRepository,
) -> AuthenticatedSession:
    """Verify credentials and issue a fresh session, or raise `InvalidCredentialsError`.

    The error never distinguishes an unknown email from a wrong password (User Story 6).
    """
    credentials = user_repository.get_credentials_by_email_key(normalize_email(email))
    if credentials is None or not verify_password(password, credentials.password_hash):
        raise InvalidCredentialsError(_INVALID_CREDENTIALS_MESSAGE)

    now = clock.now()
    raw_token = generate_session_token()
    session = issue_session(
        session_id=AuthSessionId(uuid4()),
        user_id=credentials.user.id,
        token_hash=hash_session_token(raw_token),
        now=now,
    )
    auth_session_repository.add(session)

    log.info("user_logged_in", user_id=str(credentials.user.id))
    return AuthenticatedSession(user=credentials.user, session=session, raw_token=raw_token)


def change_user_password(
    *,
    user: User,
    current_password: str,
    new_password: str,
    current_session_id: AuthSessionId,
    user_repository: UserRepository,
    auth_session_repository: AuthSessionRepository,
) -> None:
    """Verify the current password, set a new one, and revoke every other session.

    Raises `InvalidCredentialsError` when `current_password` does not match the User's stored
    hash, and `InvalidPasswordLengthError` (User Story 9) when `new_password` fails length
    validation. The caller's own session (`current_session_id`) is left untouched.
    """
    credentials = user_repository.get_credentials_by_id(user.id)
    if credentials is None or not verify_password(current_password, credentials.password_hash):
        raise InvalidCredentialsError(_INVALID_CREDENTIALS_MESSAGE)

    validate_password_length(new_password)
    user_repository.update_password(user.id, hash_password(new_password))
    auth_session_repository.revoke_all_except(user.id, current_session_id)

    log.info("password_changed", user_id=str(user.id))


def delete_user_account(*, user: User, password: str, user_repository: UserRepository) -> None:
    """Verify the password and permanently delete the User (User Story 10).

    Raises `InvalidCredentialsError` when `password` does not match the User's stored hash.
    Deletion relies on the `user`/`auth_session`/`task`/`pomodoro`/`tag`/`timer` FK
    `ON DELETE CASCADE`/`RESTRICT` chain to remove every owned row; it never settles or logs an
    in-progress Timer, which is discarded along with its row.
    """
    credentials = user_repository.get_credentials_by_id(user.id)
    if credentials is None or not verify_password(password, credentials.password_hash):
        raise InvalidCredentialsError(_INVALID_CREDENTIALS_MESSAGE)

    user_repository.delete(user.id)

    log.info("account_deleted", user_id=str(user.id))
