"""The `Task` entity, its domain errors, and the repository Protocol it needs (ADR-0002).

A Task's uniqueness key (`text_key`) is a persistence-only derived column, like `User.email_key`:
`core` computes it via `normalize_task_text`, but it never appears on this entity (ADR-0001:
core holds domain rules, not storage-shaped columns). Tags are not implemented yet (T8); `tag_ids`
exists on the entity per the spec's shape and is always empty until Tags land.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from pomodoro.core.users import UserId

TaskId = NewType("TaskId", UUID)

MAX_TASK_TEXT_LENGTH = 200


class EmptyTaskTextError(ValueError):
    """Raised when a Task's text is empty once leading/trailing whitespace is stripped."""


class TaskTextTooLongError(ValueError):
    """Raised when a Task's trimmed text exceeds `MAX_TASK_TEXT_LENGTH` characters."""


class DuplicateTaskTextError(ValueError):
    """Raised when a Task's text matches another of the same User's Active Tasks."""


class TaskNotFoundError(LookupError):
    """Raised when a Task does not exist, or does not belong to the caller."""


@dataclass(frozen=True, slots=True)
class Task:
    """A unit of work a Pomodoro can be dedicated to. Active iff `archived_at` is None."""

    id: TaskId
    user_id: UserId
    text: str
    position: int
    tag_ids: tuple[UUID, ...]
    created_at: datetime
    archived_at: datetime | None

    @property
    def is_active(self) -> bool:
        """Whether this Task is on the Active list (i.e. not archived)."""
        return self.archived_at is None


def normalize_task_text(text: str) -> str:
    """Return the comparison key for Task text: `strip().casefold()`."""
    return text.strip().casefold()


def validate_task_text(text: str) -> str:
    """Return `text` stripped, raising a domain error if it is empty or too long."""
    stripped = text.strip()
    if not stripped:
        raise EmptyTaskTextError("Task text cannot be empty.")
    if len(stripped) > MAX_TASK_TEXT_LENGTH:
        raise TaskTextTooLongError(f"Task text cannot exceed {MAX_TASK_TEXT_LENGTH} characters.")
    return stripped


def next_active_position(active_tasks: Iterable[Task]) -> int:
    """Return the position for a new Task: one before the lowest Active position, else 0."""
    positions = [task.position for task in active_tasks]
    return min(positions) - 1 if positions else 0


def ensure_unique_active_text(
    *, text_key: str, active_tasks: Iterable[Task], exclude_task_id: TaskId | None = None
) -> None:
    """Raise `DuplicateTaskTextError` if another Active Task already has this `text_key`."""
    for task in active_tasks:
        if task.id == exclude_task_id:
            continue
        if normalize_task_text(task.text) == text_key:
            raise DuplicateTaskTextError(f"A Task with this text already exists: '{task.text}'.")


class TaskRepository(Protocol):
    """Persistence Protocol for `Task`, scoped to a `UserId` (implemented by `database`)."""

    def add(self, task: Task, text_key: str) -> None:
        """Persist a newly created Task."""
        ...

    def get_by_id(self, user_id: UserId, task_id: TaskId) -> Task | None:
        """Return the caller's Task with this id, or None if absent or owned by another User."""
        ...

    def list_active(self, user_id: UserId) -> list[Task]:
        """Return the caller's Active Tasks ordered by `(position, id)`."""
        ...

    def update_text(self, user_id: UserId, task_id: TaskId, text: str, text_key: str) -> None:
        """Overwrite a Task's text and derived key."""
        ...
