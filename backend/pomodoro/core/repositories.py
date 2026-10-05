"""Framework-free repository contracts the `database` layer implements.

Pure core: no FastAPI/SQLModel/Pydantic imports. Every method is scoped to a
single User's data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from pomodoro.core.auth import UserRecord
    from pomodoro.core.entities import (
        AuthSession,
        AuthSessionId,
        Pomodoro,
        Tag,
        TagId,
        Task,
        TaskId,
        User,
        UserId,
    )
    from pomodoro.core.timer import Timer


@runtime_checkable
class UserRepository(Protocol):
    """User persistence; the one repository not scoped to a `UserId`."""

    def get_by_id(self, user_id: UserId) -> User | None:
        """Return the User by id, or `None` if it doesn't exist."""
        ...

    def get_by_email_key(self, email_key: str) -> UserRecord | None:
        """Return the User and password hash matching `email_key`, or `None`."""
        ...

    def add(self, user: User, password_hash: str) -> User:
        """Persist a new User and return it with its assigned id.

        The `id` on the given User is a placeholder; the implementation
        assigns the real one and returns a new User carrying it.
        """
        ...

    def update(self, user: User) -> User:
        """Persist changes to an existing User and return the stored result."""
        ...

    def update_password_hash(self, user_id: UserId, password_hash: str) -> None:
        """Persist a new Argon2 hash for the User, replacing the previous one."""
        ...

    def delete(self, user_id: UserId) -> None:
        """Permanently remove the User and every row that cascades off it."""
        ...


@runtime_checkable
class AuthSessionRepository(Protocol):
    """Login-session persistence; only a token's hash is ever stored."""

    def create(self, user_id: UserId, token_hash: str, expires_at: datetime) -> AuthSession:
        """Persist a new session for `user_id` and return it with its assigned id."""
        ...

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        """Return the session matching `token_hash`, or `None` if none does."""
        ...

    def touch_last_used(self, session_id: AuthSessionId, *, expires_at: datetime) -> None:
        """Renew `last_used_at` to the current time and extend `expires_at`.

        The caller (the sliding-expiry policy in `api`) decides the new
        `expires_at`; this method only persists it alongside the current time.
        """
        ...

    def revoke(self, session_id: AuthSessionId) -> None:
        """Permanently remove a single session."""
        ...

    def revoke_all_for_user(self, user_id: UserId) -> None:
        """Permanently remove every session belonging to `user_id`."""
        ...

    def revoke_all_for_user_except(self, user_id: UserId, keep_session_id: AuthSessionId) -> None:
        """Permanently remove every session for `user_id` other than `keep_session_id`."""
        ...


@runtime_checkable
class TagRepository(Protocol):
    """Tag catalog persistence, every method scoped to a `UserId`."""

    def list(self, user_id: UserId) -> list[Tag]:
        """Return the User's Tag catalog, including orphaned Tags (zero Tasks)."""
        ...

    def get_or_create_by_name(self, user_id: UserId, name: str) -> Tag:
        """Return the User's Tag matching `name`'s normalized key, creating it if absent."""
        ...

    def rename(self, user_id: UserId, tag_id: TagId, new_name: str) -> Tag:
        """Rename the User's Tag; the new name is visible on every Task carrying it."""
        ...

    def delete(self, user_id: UserId, tag_id: TagId) -> None:
        """Remove the User's Tag from the catalog and from every Task that had it."""
        ...


@runtime_checkable
class TaskRepository(Protocol):
    """Task persistence, every method scoped to a `UserId`."""

    def list_active(self, user_id: UserId) -> list[Task]:
        """Return the User's Active Tasks, in no particular order."""
        ...

    def list_archived(self, user_id: UserId) -> list[Task]:
        """Return the User's Archived Tasks, in no particular order."""
        ...

    def get(self, user_id: UserId, task_id: TaskId) -> Task | None:
        """Return the User's Task by id, or `None` if it doesn't exist."""
        ...

    def add(self, task: Task) -> Task:
        """Persist a new Task and return it with its assigned id.

        The `id` on the given Task is a placeholder; the implementation
        assigns the real one (e.g. an autoincrement primary key) and returns
        a new Task carrying it.
        """
        ...

    def update(self, task: Task) -> Task:
        """Persist changes to an existing Task and return the stored result."""
        ...

    def delete(self, user_id: UserId, task_id: TaskId) -> None:
        """Permanently remove the User's Task."""
        ...


@runtime_checkable
class TimerRepository(Protocol):
    """Per-User live Timer persistence; every User has exactly one Timer."""

    def get(self, user_id: UserId) -> Timer | None:
        """Return the User's Timer, or `None` if no row exists yet."""
        ...

    def save(self, user_id: UserId, timer: Timer) -> None:
        """Persist the User's Timer, replacing any previous state."""
        ...


@runtime_checkable
class PomodoroRepository(Protocol):
    """Pomodoro history persistence, every method scoped to a `UserId`."""

    def add(self, pomodoro: Pomodoro) -> Pomodoro:
        """Persist a new Pomodoro and return it with its assigned id.

        The `id` on the given Pomodoro is a placeholder; the implementation
        assigns the real one and returns a new Pomodoro carrying it.
        """
        ...

    def count_completed_for_user(self, user_id: UserId) -> int:
        """Return the User's total count of `completed` Pomodoros."""
        ...

    def count_completed_between(self, user_id: UserId, start: datetime, end: datetime) -> int:
        """Return the User's count of `completed` Pomodoros with `ended_at` in `[start, end)`."""
        ...

    def exists_for_task(self, user_id: UserId, task_id: TaskId) -> bool:
        """Return whether the User's Task has any Pomodoro (any status) recorded."""
        ...

    def list_between(self, user_id: UserId, start: datetime, end: datetime) -> list[Pomodoro]:
        """Return the User's Pomodoros (any status) with `ended_at` in `[start, end)`.

        Ordered by `ended_at`, ascending. Feeds History's monthly heatmap and
        day detail aggregation.
        """
        ...
