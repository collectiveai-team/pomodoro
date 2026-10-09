"""Domain-level errors shared across pomodoro.core.

Carry no HTTP concerns: pomodoro.entrypoints.app maps DomainError (and its
subclasses) to the single ErrorResponse shape via one registered exception
handler, so routers and core rules never construct HTTP responses themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pomodoro.core.entities import TaskId, Timer


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


class TaskReorderInvalidError(DomainError):
    """Raised when a reorder request's ids aren't exactly the User's Active Task ids."""

    def __init__(self) -> None:
        super().__init__(
            "Reorder must include exactly the User's current Active Task ids, each once."
        )


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


class EmailInvalidError(DomainError):
    """Raised when an email fails syntax validation."""

    def __init__(self, email: str) -> None:
        super().__init__(f"Email address {email!r} is not valid.")
        self.email = email


class DuplicateEmailError(DomainError):
    """Raised when registering an email that collides with an existing User's."""

    def __init__(self, email: str) -> None:
        super().__init__(f"An account with the email {email!r} already exists.")
        self.email = email


class PasswordLengthError(DomainError):
    """Raised when a password's length is outside the allowed range.

    Never carries the password itself, only the bounds it violated.
    """

    def __init__(self, min_length: int, max_length: int) -> None:
        super().__init__(f"Password must be between {min_length} and {max_length} characters.")
        self.min_length = min_length
        self.max_length = max_length


class InvalidTimeZoneError(DomainError):
    """Raised when a time zone isn't a valid IANA zone name (register T9, Settings T15)."""

    def __init__(self, time_zone: str) -> None:
        super().__init__(f"{time_zone!r} is not a valid time zone.")
        self.time_zone = time_zone


class TimerActionNotAllowedError(DomainError):
    """Raised when a Timer action doesn't match its current phase; `api` maps this to 409."""

    def __init__(self, action: str, timer: Timer) -> None:
        super().__init__(f"Cannot {action!r} while the Timer is in phase {timer.phase.value!r}.")
        self.action = action
        self.timer = timer


class TaskNotActiveError(DomainError):
    """Raised when starting a Pomodoro against a Task that isn't one of the User's Active Tasks."""

    def __init__(self, task_id: TaskId) -> None:
        super().__init__(f"Task {task_id} is not one of the User's Active Tasks.")
        self.task_id = task_id


class TaskInProgressError(DomainError):
    """Raised when archiving or deleting the Task currently in progress on the Timer (T14)."""

    def __init__(self, task_id: TaskId) -> None:
        super().__init__(
            f"Task {task_id} cannot be archived or deleted while it is in progress on the Timer."
        )
        self.task_id = task_id
