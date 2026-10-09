"""Task lifecycle rules (core, T4/T11): create, edit, archive, unarchive, reorder, delete.

Pure functions over `Task` snapshots scoped to a single `User` — `core` never
queries a database, so callers pass in the relevant `Task`s (and, for deletion,
whether the Task has any Pomodoro) and get back the updated snapshot(s). `Task`
carries no own counters (issue #12 spec): totals are always derived from
Pomodoros elsewhere, never cached here.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from pomodoro.core.entities import Task
from pomodoro.core.errors import (
    DuplicateTaskTextError,
    TaskHasPomodorosError,
    TaskReorderInvalidError,
    TaskTextEmptyError,
    TaskTextTooLongError,
    TaskUnarchiveCollisionError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from pomodoro.core.entities import TaskId, UserId

MAX_TASK_TEXT_LENGTH = 200


def _validate_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise TaskTextEmptyError
    if len(stripped) > MAX_TASK_TEXT_LENGTH:
        raise TaskTextTooLongError(len(stripped), MAX_TASK_TEXT_LENGTH)
    return stripped


def _active_tasks(tasks: Sequence[Task]) -> list[Task]:
    return [task for task in tasks if task.archived_at is None]


def _archived_tasks(tasks: Sequence[Task]) -> list[Task]:
    return [task for task in tasks if task.archived_at is not None]


def _find_active_duplicate(
    tasks: Sequence[Task], text_key: str, *, ignore_task_id: TaskId | None
) -> Task | None:
    for task in _active_tasks(tasks):
        if task.id != ignore_task_id and task.text_key == text_key:
            return task
    return None


def create_task(
    tasks: Sequence[Task],
    *,
    new_task_id: TaskId,
    user_id: UserId,
    text: str,
    created_at: datetime,
) -> Task:
    """Create a new Task at the front of the User's Active Tasks (position = min-1)."""
    validated_text = _validate_text(text)
    candidate = Task(
        id=new_task_id,
        user_id=user_id,
        text=validated_text,
        position=0,
        created_at=created_at,
    )
    if _find_active_duplicate(tasks, candidate.text_key, ignore_task_id=None) is not None:
        raise DuplicateTaskTextError(validated_text)
    active = _active_tasks(tasks)
    position = min((task.position for task in active), default=0) - 1
    return replace(candidate, position=position)


def edit_task_text(tasks: Sequence[Task], task: Task, *, text: str) -> Task:
    """Edit a Task's text, rejecting a collision with another of the User's Active Tasks."""
    validated_text = _validate_text(text)
    updated = replace(task, text=validated_text)
    if task.archived_at is None:
        duplicate = _find_active_duplicate(tasks, updated.text_key, ignore_task_id=task.id)
        if duplicate is not None:
            raise DuplicateTaskTextError(validated_text)
    return updated


def archive_task(task: Task, *, archived_at: datetime) -> Task:
    """Archive a Task, freezing its `position` and setting `archived_at`."""
    return replace(task, archived_at=archived_at)


def unarchive_task(tasks: Sequence[Task], task: Task) -> Task:
    """Unarchive a Task to the end of the Active list, rejecting a text collision."""
    duplicate = _find_active_duplicate(tasks, task.text_key, ignore_task_id=task.id)
    if duplicate is not None:
        raise TaskUnarchiveCollisionError(task.text)
    active = _active_tasks(tasks)
    position = max((t.position for t in active), default=-1) + 1
    return replace(task, archived_at=None, position=position)


def reorder_active_tasks(active_tasks: Sequence[Task], ordered_ids: Sequence[TaskId]) -> list[Task]:
    """Rewrite the given Active Tasks' positions to 0..n-1, following `ordered_ids`.

    `ordered_ids` must be exactly a permutation of `active_tasks`' ids — this is a
    caller contract, not a user-facing validation (api/T11 is where an invalid list
    from the User is rejected with a domain error).
    """
    tasks_by_id = {task.id: task for task in active_tasks}
    if set(ordered_ids) != set(tasks_by_id):
        raise ValueError("ordered_ids must be exactly the given active_tasks' ids")
    return [
        replace(tasks_by_id[task_id], position=index) for index, task_id in enumerate(ordered_ids)
    ]


def reorder_active_tasks_for_user(
    active_tasks: Sequence[Task], ordered_ids: Sequence[TaskId]
) -> list[Task]:
    """Reorder from a User-supplied id list, rejecting rather than partially applying it.

    `reorder_active_tasks` treats a mismatched id set as a caller-contract
    violation (`ValueError`); this wraps it with the User-facing validation
    (api/T11) that reports a clear `TaskReorderInvalidError` instead, covering a
    list that adds, drops, or repeats an id.
    """
    has_duplicates = len(ordered_ids) != len(set(ordered_ids))
    if has_duplicates or set(ordered_ids) != {task.id for task in active_tasks}:
        raise TaskReorderInvalidError
    return reorder_active_tasks(active_tasks, ordered_ids)


def ensure_task_deletable(task: Task, *, has_pomodoros: bool) -> None:
    """Raise if `task` has any Pomodoro — permanent delete is only for untouched Tasks."""
    if has_pomodoros:
        raise TaskHasPomodorosError(task.id)


def order_active_tasks(tasks: Sequence[Task]) -> list[Task]:
    """Return the User's Active Tasks ordered by `(position, id)`."""
    return sorted(_active_tasks(tasks), key=lambda task: (task.position, task.id))


def order_archived_tasks(tasks: Sequence[Task]) -> list[Task]:
    """Return the User's Archived Tasks ordered by `archived_at` descending."""
    return sorted(
        _archived_tasks(tasks),
        key=lambda task: (task.archived_at, task.id),
        reverse=True,
    )
