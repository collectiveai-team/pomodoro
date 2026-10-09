"""CES-17 · POST/PATCH/GET /api/v1/tasks (Tasks: create and edit; User Stories 14, 16-19, 21).

Same FastAPI type-hint-resolution caveat as `auth/routers.py`: every annotated name must be a
real, module-level import, never `TYPE_CHECKING`-only.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from pomodoro.api.v1.auth.dependencies import get_current_user
from pomodoro.api.v1.tasks.schemas.requests.create_task import CreateTaskRequest
from pomodoro.api.v1.tasks.schemas.requests.update_task import UpdateTaskRequest
from pomodoro.api.v1.tasks.schemas.responses.task import TaskResponse
from pomodoro.api.v1.tasks.use_cases import create_task, edit_task_text
from pomodoro.core.clock import Clock, get_clock
from pomodoro.core.tasks import Task, TaskId, TaskRepository
from pomodoro.core.users import User
from pomodoro.database.repositories.task import get_task_repository

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        text=task.text,
        position=task.position,
        tag_ids=list(task.tag_ids),
        created_at=task.created_at,
        archived_at=task.archived_at,
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
    return _task_response(task)


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
    return _task_response(task)


@router.get("")
def list_active(
    user: User = Depends(get_current_user),
    task_repository: TaskRepository = Depends(get_task_repository),
) -> list[TaskResponse]:
    """List the caller's Active Tasks ordered by `(position, id)`."""
    return [_task_response(task) for task in task_repository.list_active(user.id)]
