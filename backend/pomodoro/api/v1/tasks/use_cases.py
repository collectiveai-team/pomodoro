"""Create and edit Task use cases: the orchestration `routers.py` delegates to (T6)."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import uuid4

from pomodoro.core.logger import get_logger
from pomodoro.core.tasks import (
    Task,
    TaskId,
    TaskNotFoundError,
    TaskRepository,
    ensure_unique_active_text,
    next_active_position,
    normalize_task_text,
    validate_task_text,
)

if TYPE_CHECKING:
    from pomodoro.core.clock import Clock
    from pomodoro.core.users import UserId

log = get_logger(__name__)


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
