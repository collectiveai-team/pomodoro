"""Task lifecycle use cases: the orchestration `routers.py` delegates to (T6, T7)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from uuid import uuid4

from pomodoro.api.v1.tags.use_cases import resolve_tag_ids_by_names
from pomodoro.core.logger import get_logger
from pomodoro.core.tasks import (
    Task,
    TaskHasRecordedPomodorosError,
    TaskId,
    TaskNotFoundError,
    TaskRepository,
    ensure_reorder_covers_active_tasks,
    ensure_unique_active_text,
    next_active_position,
    next_unarchive_position,
    normalize_task_text,
    validate_task_text,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pomodoro.core.clock import Clock
    from pomodoro.core.tags import TagRepository
    from pomodoro.core.users import UserId

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TaskListing:
    """A page of Tasks plus both tab-badge counts, for the list endpoints (T7)."""

    tasks: list[Task]
    active_count: int
    archived_count: int
    task_ids_with_pomodoros: frozenset[TaskId]


def create_task(
    *, user_id: UserId, text: str, clock: Clock, task_repository: TaskRepository
) -> Task:
    """Validate and create a Task positioned before all of the caller's Active Tasks."""
    validated_text = validate_task_text(text)
    text_key = normalize_task_text(validated_text)
    active_tasks = task_repository.list_active(user_id)
    ensure_unique_active_text(text_key=text_key, active_tasks=active_tasks)

    task = Task(
        id=TaskId(uuid4()),
        user_id=user_id,
        text=validated_text,
        position=next_active_position(active_tasks),
        tag_ids=(),
        created_at=clock.now(),
        archived_at=None,
    )
    task_repository.add(task, text_key)

    log.info("task_created", task_id=str(task.id))
    return task


def edit_task_text(
    *, user_id: UserId, task_id: TaskId, text: str, task_repository: TaskRepository
) -> Task:
    """Validate and overwrite a Task's text, under the same rules as creation.

    Raises `TaskNotFoundError` when the Task does not exist or belongs to another User.
    """
    task = task_repository.get_by_id(user_id, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found.")

    validated_text = validate_task_text(text)
    text_key = normalize_task_text(validated_text)
    active_tasks = task_repository.list_active(user_id)
    ensure_unique_active_text(text_key=text_key, active_tasks=active_tasks, exclude_task_id=task_id)

    task_repository.update_text(user_id, task_id, validated_text, text_key)

    log.info("task_text_edited", task_id=str(task_id))
    return replace(task, text=validated_text)


def archive_task(
    *, user_id: UserId, task_id: TaskId, clock: Clock, task_repository: TaskRepository
) -> Task:
    """Freeze the Task's `position` and set `archived_at` to now.

    Raises `TaskNotFoundError` when the Task does not exist or belongs to another User.
    """
    task = task_repository.get_by_id(user_id, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found.")

    archived_at = clock.now()
    task_repository.archive(user_id, task_id, archived_at)

    log.info("task_archived", task_id=str(task_id))
    return replace(task, archived_at=archived_at)


def unarchive_task(*, user_id: UserId, task_id: TaskId, task_repository: TaskRepository) -> Task:
    """Clear `archived_at` and append the Task at the end of the caller's Active list.

    Raises `TaskNotFoundError` when the Task does not exist or belongs to another User, and
    `DuplicateTaskTextError` when its text collides with one of the caller's Active Tasks.
    """
    task = task_repository.get_by_id(user_id, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found.")

    active_tasks = task_repository.list_active(user_id)
    ensure_unique_active_text(text_key=normalize_task_text(task.text), active_tasks=active_tasks)
    position = next_unarchive_position(active_tasks)
    task_repository.unarchive(user_id, task_id, position)

    log.info("task_unarchived", task_id=str(task_id))
    return replace(task, archived_at=None, position=position)


def reorder_tasks(
    *, user_id: UserId, ordered_task_ids: Sequence[TaskId], task_repository: TaskRepository
) -> list[Task]:
    """Rewrite the caller's Active Tasks' `position` as `0..n-1`, following `ordered_task_ids`.

    Raises `TaskReorderMismatchError` unless `ordered_task_ids` is exactly a permutation of the
    caller's current Active Task ids.
    """
    active_tasks = task_repository.list_active(user_id)
    ensure_reorder_covers_active_tasks(ordered_task_ids, active_tasks)
    task_repository.reorder(user_id, ordered_task_ids)

    log.info("tasks_reordered", user_id=str(user_id))
    return task_repository.list_active(user_id)


def delete_task(*, user_id: UserId, task_id: TaskId, task_repository: TaskRepository) -> None:
    """Permanently remove a Task that never had a Pomodoro recorded against it.

    Raises `TaskNotFoundError` when the Task does not exist or belongs to another User, and
    `TaskHasRecordedPomodorosError` when at least one Pomodoro was recorded against it.
    """
    task = task_repository.get_by_id(user_id, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found.")

    if task_id in task_repository.task_ids_with_pomodoros(user_id):
        raise TaskHasRecordedPomodorosError(
            f"Task {task_id} has at least one Pomodoro recorded and cannot be deleted."
        )

    task_repository.delete(user_id, task_id)

    log.info("task_deleted", task_id=str(task_id))


def set_task_tags(
    *,
    user_id: UserId,
    task_id: TaskId,
    names: Sequence[str],
    task_repository: TaskRepository,
    tag_repository: TagRepository,
) -> Task:
    """Set a Task's Tags from a name list, creating or reusing each by normalized key.

    Raises `TaskNotFoundError` when the Task does not exist or belongs to another User.
    """
    task = task_repository.get_by_id(user_id, task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id} not found.")

    tag_ids = resolve_tag_ids_by_names(user_id=user_id, names=names, tag_repository=tag_repository)
    task_repository.set_tags(user_id, task_id, tag_ids)

    log.info("task_tags_set", task_id=str(task_id))
    return replace(task, tag_ids=tuple(tag_ids))


def list_active_tasks(*, user_id: UserId, task_repository: TaskRepository) -> TaskListing:
    """Return the caller's Active Tasks plus both tab-badge counts."""
    tasks = task_repository.list_active(user_id)
    return TaskListing(
        tasks=tasks,
        active_count=len(tasks),
        archived_count=task_repository.count_archived(user_id),
        task_ids_with_pomodoros=task_repository.task_ids_with_pomodoros(user_id),
    )


def list_archived_tasks(*, user_id: UserId, task_repository: TaskRepository) -> TaskListing:
    """Return the caller's Archived Tasks plus both tab-badge counts."""
    tasks = task_repository.list_archived(user_id)
    return TaskListing(
        tasks=tasks,
        active_count=task_repository.count_active(user_id),
        archived_count=len(tasks),
        task_ids_with_pomodoros=task_repository.task_ids_with_pomodoros(user_id),
    )
