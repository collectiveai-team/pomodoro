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

    from pomodoro.core.entities import AuthSession, AuthSessionId, Task, TaskId, User, UserId


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

    def delete_all_for_user_except(
        self, user_id: UserId, *, keep_session_id: AuthSessionId
    ) -> None:
        """Revoke every AuthSession belonging to `user_id` except `keep_session_id`."""
        ...


class TaskRepository(Protocol):
    """Persistence port for `Task` (`database.task_repository.SqlTaskRepository`, T10).

    Every method takes the owning `UserId` explicitly and the implementation
    filters by it at the SQL level, so a caller can never reach another User's
    Task even by mistake (cross-User leakage is impossible by construction).
    """

    def add(self, *, user_id: UserId, text: str, position: int, created_at: datetime) -> Task:
        """Create a new Task, raising `DuplicateTaskTextError` on an Active-text collision."""
        ...

    def list_for_user(self, user_id: UserId) -> list[Task]:
        """Return every Task (Active and Archived) belonging to `user_id`."""
        ...

    def get(self, user_id: UserId, task_id: TaskId) -> Task | None:
        """Return `user_id`'s Task with `task_id`, or `None` if it doesn't exist for them."""
        ...

    def update_text(self, user_id: UserId, task_id: TaskId, *, text: str) -> Task:
        """Persist `text` on `user_id`'s Task with `task_id`."""
        ...

    def delete(self, user_id: UserId, task_id: TaskId) -> None:
        """Permanently delete `user_id`'s Task with `task_id`, if it exists."""
        ...

    def has_pomodoro(self, user_id: UserId, task_id: TaskId) -> bool:
        """Return whether `user_id`'s Task with `task_id` has any recorded Pomodoro."""
        ...

    def task_ids_with_pomodoros(self, user_id: UserId) -> frozenset[TaskId]:
        """Return the ids of `user_id`'s Tasks that have at least one recorded Pomodoro."""
        ...
