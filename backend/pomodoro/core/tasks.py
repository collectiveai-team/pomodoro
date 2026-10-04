"""Task lifecycle rules: create, edit, archive, unarchive, reorder, delete.

Pure core: no FastAPI/SQLModel/Pydantic imports. Every rule here is scoped to a
single User; callers are responsible for passing in only that User's Tasks.

Note on ids: `create_task` takes the new Task's id as a parameter because
assigning one is a persistence concern (autoincrement primary key) outside
pure core's reach — the repository implementation is expected to supply it
(see `TaskRepository.add` in `pomodoro.core.repositories`).
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from pomodoro.core.entities import Task
from pomodoro.core.errors import (
    MAX_TASK_TEXT_LENGTH,
    DuplicateActiveTaskTextError,
    TaskHasPomodorosError,
    TaskReorderMismatchError,
    TaskTextEmptyError,
    TaskTextTooLongError,
    UnarchiveCollisionError,
)
from pomodoro.core.normalization import normalize_key

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from pomodoro.core.entities import TagId, TaskId, UserId


def validate_task_text(text: str) -> str:
    """Return the trimmed text, or raise if it is empty or too long."""
    stripped = text.strip()
    if not stripped:
        raise TaskTextEmptyError
    if len(stripped) > MAX_TASK_TEXT_LENGTH:
        raise TaskTextTooLongError
    return stripped


def _active_text_collides(
    text: str,
    active_tasks: Sequence[Task],
    *,
    exclude_task_id: TaskId | None = None,
) -> bool:
    key = normalize_key(text)
    return any(
        task.id != exclude_task_id and normalize_key(task.text) == key for task in active_tasks
    )


def ensure_unique_active_text(
    text: str,
    active_tasks: Sequence[Task],
    *,
    exclude_task_id: TaskId | None = None,
) -> None:
    """Raise if `text` normalizes to the same key as one of `active_tasks`."""
    if _active_text_collides(text, active_tasks, exclude_task_id=exclude_task_id):
        raise DuplicateActiveTaskTextError


def compute_create_position(active_tasks: Sequence[Task]) -> int:
    """Return the position a new Task gets: current minimum minus one."""
    positions = [task.position for task in active_tasks]
    return (min(positions) - 1) if positions else 0


def create_task(
    *,
    id: TaskId,
    user_id: UserId,
    text: str,
    active_tasks: Sequence[Task],
    created_at: datetime,
    tag_ids: tuple[TagId, ...] = (),
) -> Task:
    """Validate and build a new Active Task, first among `active_tasks`."""
    stripped = validate_task_text(text)
    ensure_unique_active_text(stripped, active_tasks)
    position = compute_create_position(active_tasks)
    return Task(
        id=id,
        user_id=user_id,
        text=stripped,
        position=position,
        tag_ids=tag_ids,
        created_at=created_at,
        archived_at=None,
    )


def edit_task_text(task: Task, new_text: str, active_tasks: Sequence[Task]) -> Task:
    """Apply create's validation rules to an edit; duplicates only matter while Active."""
    stripped = validate_task_text(new_text)
    if task.archived_at is None:
        ensure_unique_active_text(stripped, active_tasks, exclude_task_id=task.id)
    return replace(task, text=stripped)


def archive_task(task: Task, archived_at: datetime) -> Task:
    """Freeze the Task's position and mark it archived."""
    return replace(task, archived_at=archived_at)


def unarchive_task(task: Task, active_tasks: Sequence[Task]) -> Task:
    """Clear `archived_at` and move the Task to the end of Active Tasks."""
    if _active_text_collides(task.text, active_tasks):
        raise UnarchiveCollisionError
    positions = [t.position for t in active_tasks]
    next_position = (max(positions) + 1) if positions else 0
    return replace(task, archived_at=None, position=next_position)


def reorder_active_tasks(active_tasks: Sequence[Task], ordered_ids: Sequence[TaskId]) -> list[Task]:
    """Rewrite `ordered_ids` as positions 0..n-1; reject a mismatched set of ids."""
    current_ids = {task.id for task in active_tasks}
    if len(ordered_ids) != len(current_ids) or set(ordered_ids) != current_ids:
        raise TaskReorderMismatchError
    by_id = {task.id: task for task in active_tasks}
    return [replace(by_id[task_id], position=index) for index, task_id in enumerate(ordered_ids)]


def sort_active_tasks(tasks: Sequence[Task]) -> list[Task]:
    """Sort Active Tasks by (position, id)."""
    return sorted(tasks, key=lambda task: (task.position, task.id))


def sort_archived_tasks(tasks: Sequence[Task]) -> list[Task]:
    """Sort Archived Tasks by `archived_at` descending."""
    return sorted(tasks, key=lambda task: task.archived_at, reverse=True)  # type: ignore[arg-type,return-value]


def ensure_task_deletable(*, has_pomodoros: bool) -> None:
    """Raise if the Task has any Pomodoro (completed or interrupted-logged) recorded."""
    if has_pomodoros:
        raise TaskHasPomodorosError
