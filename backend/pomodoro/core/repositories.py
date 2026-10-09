"""Persistence port Protocols for `User` and `AuthSession` (core, T7).

No framework types appear in any signature here: `database/user_repository.py`
and `database/auth_session_repository.py` satisfy these Protocols but hand back
`core.entities` dataclasses, never SQLModel rows or raw dicts (CES-79, ADR-0002).
`core` only declares the port - it never imports `pomodoro.database`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from pomodoro.core.entities import AuthSession, AuthSessionId, User, UserId


class UserRepository(Protocol):
    """Persistence port for `User` (`database.user_repository.SqlUserRepository`)."""

    def add(self, *, email: str, password_hash: str, time_zone: str, created_at: datetime) -> User:
        """Create a new User, raising `DuplicateEmailError` on an `email_key` collision."""
        ...

    def get_by_id(self, user_id: UserId) -> User | None:
        """Return the User with `user_id`, or `None` if it doesn't exist."""
        ...

    def get_by_email(self, email: str) -> User | None:
        """Return the User whose `email_key` matches `email`, or `None`."""
        ...

    def get_password_hash(self, user_id: UserId) -> str | None:
        """Return the stored Argon2 hash for `user_id`, or `None`; never the raw password."""
        ...

    def update(self, user: User) -> User:
        """Persist `user`'s mutable preference fields (time zone, alarm, notifications)."""
        ...

    def update_password_hash(self, user_id: UserId, password_hash: str) -> None:
        """Replace the stored Argon2 hash for `user_id`."""
        ...

    def delete(self, user_id: UserId) -> None:
        """Permanently delete the User with `user_id`, if it exists."""
        ...


class AuthSessionRepository(Protocol):
    """Persistence port for `AuthSession` (`database.SqlAuthSessionRepository` implements it)."""

    def add(
        self,
        *,
        user_id: UserId,
        token_hash: str,
        created_at: datetime,
        last_used_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        """Create a new AuthSession for `user_id`."""
        ...

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        """Return the AuthSession matching `token_hash`, or `None`."""
        ...

    def update(self, session: AuthSession) -> AuthSession:
        """Persist `session`'s mutable fields (`last_used_at`, `expires_at`)."""
        ...

    def delete(self, session_id: AuthSessionId) -> None:
        """Revoke (delete) the AuthSession with `session_id`, if it exists."""
        ...

    def delete_all_for_user(self, user_id: UserId) -> None:
        """Revoke every AuthSession belonging to `user_id`."""
        ...
