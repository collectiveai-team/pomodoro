"""The `Task` entity, its domain errors, and the repository Protocol it needs (ADR-0002).

A Task's uniqueness key (`text_key`) is a persistence-only derived column, like `User.email_key`:
`core` computes it via `normalize_task_text`, but it never appears on this entity (ADR-0001:
core holds domain rules, not storage-shaped columns). `tag_ids` holds the ids of the `core.tags`
Tags assigned to this Task (T8); a Task only ever stores a Tag's id, never a copy of its name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType, Protocol
from uuid import UUID

from pomodoro.core.timer import TimerPhase

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from datetime import datetime

    from pomodoro.core.tags import TagId
    from pomodoro.core.timer import Timer
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


class TaskReorderMismatchError(ValueError):
    """Raised when a reorder request's ids aren't exactly the caller's Active Task ids, once."""


class TaskHasRecordedPomodorosError(ValueError):
    """Raised when deleting a Task that has at least one Pomodoro recorded against it."""


class TaskInUseByTimerError(ValueError):
    """Raised when archiving or deleting a Task the caller's Timer references, non-Idle."""


@dataclass(frozen=True, slots=True)
class Task:
    """A unit of work a Pomodoro can be dedicated to. Active iff `archived_at` is None."""

    id: TaskId
    user_id: UserId
    text: str
    position: int
    tag_ids: tuple[TagId, ...]
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


def next_unarchive_position(active_tasks: Iterable[Task]) -> int:
    """Return the position for an unarchived Task: one past the highest Active position, else 0."""
    positions = [task.position for task in active_tasks]
    return max(positions) + 1 if positions else 0


def ensure_reorder_covers_active_tasks(
    ordered_task_ids: Sequence[TaskId], active_tasks: Iterable[Task]
) -> None:
    """Raise `TaskReorderMismatchError` unless `ordered_task_ids` is a permutation of Active ids."""
    active_ids = {task.id for task in active_tasks}
    if len(ordered_task_ids) != len(set(ordered_task_ids)) or set(ordered_task_ids) != active_ids:
        raise TaskReorderMismatchError(
            "Reorder must include exactly the caller's Active Task ids, each exactly once."
        )


def ensure_unique_active_text(
    *, text_key: str, active_tasks: Iterable[Task], exclude_task_id: TaskId | None = None
) -> None:
    """Raise `DuplicateTaskTextError` if another Active Task already has this `text_key`."""
    for task in active_tasks:
        if task.id == exclude_task_id:
            continue
        if normalize_task_text(task.text) == text_key:
            raise DuplicateTaskTextError(f"A Task with this text already exists: '{task.text}'.")


def ensure_task_not_in_timer_use(*, task_id: TaskId, timer: Timer) -> None:
    """Raise `TaskInUseByTimerError` if `timer` is non-Idle and currently references `task_id`."""
    if timer.phase is not TimerPhase.IDLE and timer.task_id == task_id:
        raise TaskInUseByTimerError(
            f"Task {task_id} is referenced by the caller's Timer and cannot be "
            "archived or deleted while it is not Idle."
        )


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

    def list_archived(self, user_id: UserId) -> list[Task]:
        """Return the caller's Archived Tasks ordered by `archived_at` descending."""
        ...

    def count_active(self, user_id: UserId) -> int:
        """Return the number of the caller's Active Tasks."""
        ...

    def count_archived(self, user_id: UserId) -> int:
        """Return the number of the caller's Archived Tasks."""
        ...

    def archive(self, user_id: UserId, task_id: TaskId, archived_at: datetime) -> None:
        """Freeze `position` and set `archived_at` on the caller's Task."""
        ...

    def unarchive(self, user_id: UserId, task_id: TaskId, position: int) -> None:
        """Clear `archived_at` and set the caller's Task to `position`."""
        ...

    def reorder(self, user_id: UserId, ordered_task_ids: Sequence[TaskId]) -> None:
        """Rewrite the caller's Active Tasks' `position` as `0..n-1`, following this order."""
        ...

    def delete(self, user_id: UserId, task_id: TaskId) -> None:
        """Permanently remove the caller's Task."""
        ...

    def set_tags(self, user_id: UserId, task_id: TaskId, tag_ids: Sequence[TagId]) -> None:
        """Replace the caller's Task's Tag assignments with exactly `tag_ids`."""
        ...

    def task_ids_with_pomodoros(self, user_id: UserId) -> frozenset[TaskId]:
        """Return the ids of the caller's Tasks that have at least one Pomodoro recorded."""
        ...
