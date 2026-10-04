"""Domain errors: every message here is safe to show directly to the User."""

from __future__ import annotations

MAX_TASK_TEXT_LENGTH = 200
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


class DomainError(Exception):
    """Base for every core-layer error; `str(error)` is the user-facing message."""


class TaskTextEmptyError(DomainError):
    """Raised when a Task's text is empty after stripping whitespace."""

    def __init__(self) -> None:
        super().__init__("El texto de la tarea no puede estar vacío.")


class TaskTextTooLongError(DomainError):
    """Raised when a Task's text exceeds `MAX_TASK_TEXT_LENGTH`."""

    def __init__(self) -> None:
        super().__init__(
            f"El texto de la tarea no puede superar los {MAX_TASK_TEXT_LENGTH} caracteres."
        )


class DuplicateActiveTaskTextError(DomainError):
    """Raised when a Task's text matches another of the User's Active Tasks."""

    def __init__(self) -> None:
        super().__init__("Ya existe una tarea activa con ese texto.")


class UnarchiveCollisionError(DomainError):
    """Raised when unarchiving a Task would collide with an Active Task's text."""

    def __init__(self) -> None:
        super().__init__("No se puede desarchivar: ya existe una tarea activa con ese texto.")


class TaskHasPomodorosError(DomainError):
    """Raised when permanently deleting a Task that has recorded Pomodoros."""

    def __init__(self) -> None:
        super().__init__("No se puede borrar una tarea con pomodoros registrados.")


class TaskReorderMismatchError(DomainError):
    """Raised when a reorder's id list doesn't match the User's Active Tasks."""

    def __init__(self) -> None:
        super().__init__("La lista de reordenamiento no coincide con las tareas activas.")


class TaskInProgressError(DomainError):
    """Raised when archiving or deleting the Task the User's Timer is running on."""

    def __init__(self) -> None:
        super().__init__("No se puede archivar ni borrar la tarea en curso.")


class TagNameEmptyError(DomainError):
    """Raised when a Tag's name is empty after stripping whitespace."""

    def __init__(self) -> None:
        super().__init__("El nombre de la etiqueta no puede estar vacío.")


class DuplicateTagNameError(DomainError):
    """Raised when a Tag's name matches another of the User's Tags."""

    def __init__(self) -> None:
        super().__init__("Ya existe una etiqueta con ese nombre.")


class InvalidEmailError(DomainError):
    """Raised when an email fails format validation."""

    def __init__(self) -> None:
        super().__init__("El email no es válido.")


class EmailAlreadyRegisteredError(DomainError):
    """Raised when registering an email that already belongs to a User."""

    def __init__(self) -> None:
        super().__init__("Ese email ya está registrado.")


class InvalidPasswordLengthError(DomainError):
    """Raised when a password's length falls outside the allowed range."""

    def __init__(self) -> None:
        super().__init__(
            f"La contraseña debe tener entre {MIN_PASSWORD_LENGTH} y "
            f"{MAX_PASSWORD_LENGTH} caracteres."
        )
