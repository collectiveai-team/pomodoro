"""Tasks API: list, create, edit, delete, filter (T10).

Thin handlers: validation and lifecycle rules delegate to `core.tasks`/
`core.filtering`, and persistence delegates to the T10 `SqlTaskRepository`
(CES-18), scoped to the authenticated User's `UserId` on every call so
cross-User leakage is impossible by construction. Reorder/archive/unarchive
(T11) and Tag assignment (T12) are out of this ticket's scope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from pomodoro.api.v1 import dependencies as deps
from pomodoro.api.v1.schemas.requests.tasks import CreateTaskRequest, EditTaskTextRequest
from pomodoro.api.v1.schemas.responses.tasks import TaskListResponse, TaskResponse
from pomodoro.api.v1.session import require_json_content_type
from pomodoro.core.entities import TagId, TaskId
from pomodoro.core.filtering import NO_TAG, filter_tasks
from pomodoro.core.tasks import (
    create_task,
    edit_task_text,
    ensure_task_deletable,
    order_active_tasks,
    order_archived_tasks,
)
from pomodoro.database.task_repository import SqlTaskRepository

if TYPE_CHECKING:
    from pomodoro.core.entities import AuthSession, Task

router = APIRouter(
    prefix="/tasks", tags=["tasks"], dependencies=[Depends(require_json_content_type)]
)

# A placeholder: `core.tasks.create_task` takes a `new_task_id` to build the candidate
# Task it validates, but the real id is only assigned once `SqlTaskRepository.add`
# persists the row - this value is never read back from the created Task.
_UNASSIGNED_TASK_ID = TaskId(0)


def _to_response(task: Task, *, deletable: bool) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        text=task.text,
        position=task.position,
        status=task.status.value,
        created_at=task.created_at,
        archived_at=task.archived_at,
        tag_ids=sorted(task.tag_ids),
        deletable=deletable,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")


@router.get("")
def list_tasks(
    name_query: str = Query(""),
    tag_ids: list[int] = Query(default=[]),
    no_tag: bool = Query(False),
    task_status: Literal["active", "archived"] = Query("active", alias="status"),
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TaskListResponse:
    """List the authenticated User's Active or Archived Tasks, filtered (spec story 45)."""
    repo = SqlTaskRepository(db_session)
    tasks = repo.list_for_user(auth_session.user_id)

    selected_tags = {TagId(tag_id) for tag_id in tag_ids}
    if no_tag:
        selected_tags.add(NO_TAG)
    filtered = filter_tasks(tasks, name_query, selected_tags)
    ordered = (
        order_active_tasks(filtered) if task_status == "active" else order_archived_tasks(filtered)
    )

    has_pomodoro_ids = repo.task_ids_with_pomodoros(auth_session.user_id)
    return TaskListResponse(
        items=[_to_response(task, deletable=task.id not in has_pomodoro_ids) for task in ordered],
        active_count=len(order_active_tasks(tasks)),
        archived_count=len(order_archived_tasks(tasks)),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create(
    payload: CreateTaskRequest,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TaskResponse:
    """Create a new Task at the front of the User's Active Tasks."""
    repo = SqlTaskRepository(db_session)
    tasks = repo.list_for_user(auth_session.user_id)
    now = datetime.now(UTC)
    validated = create_task(
        tasks,
        new_task_id=_UNASSIGNED_TASK_ID,
        user_id=auth_session.user_id,
        text=payload.text,
        created_at=now,
    )
    created = repo.add(
        user_id=auth_session.user_id,
        text=validated.text,
        position=validated.position,
        created_at=now,
    )
    return _to_response(created, deletable=True)


@router.put("/{task_id}")
def edit_text(
    task_id: int,
    payload: EditTaskTextRequest,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TaskResponse:
    """Edit a Task's text, subject to the same validation as creation."""
    repo = SqlTaskRepository(db_session)
    task = repo.get(auth_session.user_id, TaskId(task_id))
    if task is None:
        raise _not_found()
    tasks = repo.list_for_user(auth_session.user_id)
    validated = edit_task_text(tasks, task, text=payload.text)
    updated = repo.update_text(auth_session.user_id, TaskId(task_id), text=validated.text)
    deletable = not repo.has_pomodoro(auth_session.user_id, TaskId(task_id))
    return _to_response(updated, deletable=deletable)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    task_id: int,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> None:
    """Permanently delete a Task that never received a Pomodoro."""
    repo = SqlTaskRepository(db_session)
    task = repo.get(auth_session.user_id, TaskId(task_id))
    if task is None:
        raise _not_found()
    has_pomodoro = repo.has_pomodoro(auth_session.user_id, TaskId(task_id))
    ensure_task_deletable(task, has_pomodoros=has_pomodoro)
    repo.delete(auth_session.user_id, TaskId(task_id))
