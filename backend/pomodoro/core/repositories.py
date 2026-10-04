"""Framework-free repository contracts the `database` layer implements.

Pure core: no FastAPI/SQLModel/Pydantic imports. Every method is scoped to a
single User's data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pomodoro.core.entities import Task, TaskId, UserId


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
