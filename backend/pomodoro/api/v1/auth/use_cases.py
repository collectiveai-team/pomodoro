"""Register-with-auto-login use case: the orchestration `routers.py` delegates to."""

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
from pomodoro.core.passwords import hash_password
from pomodoro.core.users import (
    DuplicateEmailError,
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


@dataclass(frozen=True, slots=True)
class RegisteredSession:
    """What a successful registration produces.

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
) -> RegisteredSession:
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
    return RegisteredSession(user=user, session=session, raw_token=raw_token)
