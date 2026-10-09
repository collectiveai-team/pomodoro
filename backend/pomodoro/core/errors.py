"""Domain-level errors shared across pomodoro.core.

Carry no HTTP concerns: pomodoro.entrypoints.app maps DomainError (and its
subclasses) to the single ErrorResponse shape via one registered exception
handler, so routers and core rules never construct HTTP responses themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pomodoro.core.entities import TaskId


class DomainError(Exception):
    """Base class for errors raised by core domain rules."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TaskTextEmptyError(DomainError):
    """Raised when a Task's text is empty once surrounding whitespace is stripped."""

    def __init__(self) -> None:
        super().__init__("Task text cannot be empty.")


class TaskTextTooLongError(DomainError):
    """Raised when a Task's text exceeds the maximum allowed length."""

    def __init__(self, length: int, max_length: int) -> None:
        super().__init__(f"Task text cannot exceed {max_length} characters (got {length}).")
        self.length = length
        self.max_length = max_length


class DuplicateTaskTextError(DomainError):
    """Raised when a Task's text collides with one of the User's other Active Tasks."""

    def __init__(self, text: str) -> None:
        super().__init__(f"An Active Task with the text {text!r} already exists.")
        self.text = text


class TaskUnarchiveCollisionError(DomainError):
    """Raised when unarchiving a Task would collide with an existing Active Task."""

    def __init__(self, text: str) -> None:
        super().__init__(f"Cannot unarchive: an Active Task with the text {text!r} already exists.")
        self.text = text


class TaskHasPomodorosError(DomainError):
    """Raised when permanently deleting a Task that has at least one Pomodoro."""

    def __init__(self, task_id: TaskId) -> None:
        super().__init__(
            f"Task {task_id} cannot be deleted because it has recorded Pomodoros; "
            "archive it instead."
        )
        self.task_id = task_id


class TagNameEmptyError(DomainError):
    """Raised when a Tag's name is empty once surrounding whitespace is stripped."""

    def __init__(self) -> None:
        super().__init__("Tag name cannot be empty.")


class TagRenameCollisionError(DomainError):
    """Raised when renaming a Tag would collide with another of the User's Tags."""

    def __init__(self, name: str) -> None:
        super().__init__(f"A Tag named {name!r} already exists.")
        self.name = name
