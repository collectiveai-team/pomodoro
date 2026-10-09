"""CES-17 · Task lifecycle endpoints (create/edit T6; archive/unarchive/reorder/delete T7).

Same FastAPI type-hint-resolution caveat as `auth/routers.py`: every annotated name must be a
real, module-level import, never `TYPE_CHECKING`-only.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from pomodoro.api.v1.auth.dependencies import get_current_user
from pomodoro.api.v1.tasks.schemas.requests.create_task import CreateTaskRequest
from pomodoro.api.v1.tasks.schemas.requests.reorder_tasks import ReorderTasksRequest
from pomodoro.api.v1.tasks.schemas.requests.set_task_tags import SetTaskTagsRequest
from pomodoro.api.v1.tasks.schemas.requests.update_task import UpdateTaskRequest
from pomodoro.api.v1.tasks.schemas.responses.task import TaskResponse
from pomodoro.api.v1.tasks.schemas.responses.task_list import TaskListResponse
from pomodoro.api.v1.tasks.use_cases import (
    TaskListing,
    archive_task,
    create_task,
    delete_task,
    edit_task_text,
    list_active_tasks,
    list_archived_tasks,
    reorder_tasks,
    set_task_tags,
    unarchive_task,
)
from pomodoro.core.clock import Clock, get_clock
from pomodoro.core.tags import TagRepository
from pomodoro.core.tasks import Task, TaskId, TaskRepository
from pomodoro.core.users import User
from pomodoro.database.repositories.tag import get_tag_repository
from pomodoro.database.repositories.task import get_task_repository

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_response(task: Task, *, deletable: bool) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        text=task.text,
        position=task.position,
        tag_ids=list(task.tag_ids),
        created_at=task.created_at,
        archived_at=task.archived_at,
        deletable=deletable,
    )


def _task_listing_response(listing: TaskListing) -> TaskListResponse:
    return TaskListResponse(
        tasks=[
            _task_response(task, deletable=task.id not in listing.task_ids_with_pomodoros)
            for task in listing.tasks
        ],
        active_count=listing.active_count,
        archived_count=listing.archived_count,
    )


@router.post("", status_code=201)
def create(
    payload: CreateTaskRequest,
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> TaskResponse:
    """Create a Task positioned before all of the caller's existing Active Tasks."""
    task = create_task(
        user_id=user.id, text=payload.text, clock=clock, task_repository=task_repository
    )
    return _task_response(task, deletable=True)


@router.patch("/{task_id}")
def update(
    task_id: UUID,
    payload: UpdateTaskRequest,
    user: User = Depends(get_current_user),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> TaskResponse:
    """Edit a Task's text, scoped to the caller, under the same validation as creation."""
    task = edit_task_text(
        user_id=user.id,
        task_id=TaskId(task_id),
        text=payload.text,
        task_repository=task_repository,
    )
    deletable = task.id not in task_repository.task_ids_with_pomodoros(user.id)
    return _task_response(task, deletable=deletable)


@router.patch("/{task_id}/tags")
def update_tags(
    task_id: UUID,
    payload: SetTaskTagsRequest,
    user: User = Depends(get_current_user),
    task_repository: TaskRepository = Depends(get_task_repository),
    tag_repository: TagRepository = Depends(get_tag_repository),
) -> TaskResponse:
    """Set the Task's Tags from a name list, creating or reusing each by normalized key."""
    task = set_task_tags(
        user_id=user.id,
        task_id=TaskId(task_id),
        names=payload.names,
        task_repository=task_repository,
        tag_repository=tag_repository,
    )
    deletable = task.id not in task_repository.task_ids_with_pomodoros(user.id)
    return _task_response(task, deletable=deletable)


@router.get("")
def list_active(
    user: User = Depends(get_current_user),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> TaskListResponse:
    """List the caller's Active Tasks ordered by `(position, id)`, with both tab-badge counts."""
    listing = list_active_tasks(user_id=user.id, task_repository=task_repository)
    return _task_listing_response(listing)


@router.get("/archived")
def list_archived(
    user: User = Depends(get_current_user),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> TaskListResponse:
    """List the caller's Archived Tasks ordered by `archived_at` descending, with both counts."""
    listing = list_archived_tasks(user_id=user.id, task_repository=task_repository)
    return _task_listing_response(listing)


@router.post("/{task_id}/archive")
def archive(
    task_id: UUID,
    user: User = Depends(get_current_user),
    clock: Clock = Depends(get_clock),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> TaskResponse:
    """Freeze the Task's position and set `archived_at`."""
    task = archive_task(
        user_id=user.id, task_id=TaskId(task_id), clock=clock, task_repository=task_repository
    )
    deletable = task.id not in task_repository.task_ids_with_pomodoros(user.id)
    return _task_response(task, deletable=deletable)


@router.post("/{task_id}/unarchive")
def unarchive(
    task_id: UUID,
    user: User = Depends(get_current_user),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> TaskResponse:
    """Clear `archived_at` and append the Task at the end of the caller's Active list."""
    task = unarchive_task(user_id=user.id, task_id=TaskId(task_id), task_repository=task_repository)
    deletable = task.id not in task_repository.task_ids_with_pomodoros(user.id)
    return _task_response(task, deletable=deletable)


@router.put("/reorder")
def reorder(
    payload: ReorderTasksRequest,
    user: User = Depends(get_current_user),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> list[TaskResponse]:
    """Rewrite the caller's Active Tasks' `position` as `0..n-1`, following the given order."""
    tasks = reorder_tasks(
        user_id=user.id,
        ordered_task_ids=[TaskId(task_id) for task_id in payload.task_ids],
        task_repository=task_repository,
    )
    ids_with_pomodoros = task_repository.task_ids_with_pomodoros(user.id)
    return [_task_response(task, deletable=task.id not in ids_with_pomodoros) for task in tasks]


@router.delete("/{task_id}", status_code=204)
def delete(
    task_id: UUID,
    user: User = Depends(get_current_user),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> None:
    """Permanently remove a Task that never had a Pomodoro recorded against it."""
    delete_task(user_id=user.id, task_id=TaskId(task_id), task_repository=task_repository)
