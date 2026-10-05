"""Tasks API: list (Active/Archived, filtered), create, edit text/tags, delete.

Per the house convention (api/<area> owns router + schemas + use case), the
orchestration lives here; `pomodoro.core.tasks`/`tags`/`filtering` supply the
framework-free rules and `pomodoro.api.session` supplies the authenticated
`User` every route below requires.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from pomodoro.api.session import get_clock, require_session
from pomodoro.core.clock import Clock
from pomodoro.core.entities import Tag, TagId, Task, TaskId, User, UserId
from pomodoro.core.errors import (
    DuplicateActiveTaskTextError,
    TagNameEmptyError,
    TaskHasPomodorosError,
    TaskInProgressError,
    TaskReorderMismatchError,
    TaskTextEmptyError,
    TaskTextTooLongError,
    UnarchiveCollisionError,
)
from pomodoro.core.filtering import SIN_ETIQUETA, filter_tasks
from pomodoro.core.repositories import (
    PomodoroRepository,
    TagRepository,
    TaskRepository,
    TimerRepository,
)
from pomodoro.core.tags import find_tag_by_name, validate_tag_name
from pomodoro.core.tasks import (
    archive_task,
    edit_task_text,
    ensure_task_deletable,
    reorder_active_tasks,
    sort_active_tasks,
    sort_archived_tasks,
    unarchive_task,
)
from pomodoro.core.tasks import (
    create_task as build_task,
)
from pomodoro.core.timer import settle_and_persist

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_task_repository() -> TaskRepository:
    """Stand in for the TaskRepository dependency until the app factory overrides it."""
    raise NotImplementedError("TaskRepository dependency must be wired by the app factory")


def get_tag_repository() -> TagRepository:
    """Stand in for the TagRepository dependency until the app factory overrides it."""
    raise NotImplementedError("TagRepository dependency must be wired by the app factory")


def get_pomodoro_repository() -> PomodoroRepository:
    """Stand in for the PomodoroRepository dependency until the app factory overrides it."""
    raise NotImplementedError("PomodoroRepository dependency must be wired by the app factory")


def get_timer_repository() -> TimerRepository:
    """Stand in for the TimerRepository dependency until the app factory overrides it.

    Owned here (rather than `api.timer`) so the Task/Timer guard below can
    depend on it without an import cycle; `api.timer` imports it from here,
    the same way it already imports `get_task_repository`/`get_pomodoro_repository`.
    """
    raise NotImplementedError("TimerRepository dependency must be wired by the app factory")


UserDep = Annotated[User, Depends(require_session)]
TaskRepoDep = Annotated[TaskRepository, Depends(get_task_repository)]
TagRepoDep = Annotated[TagRepository, Depends(get_tag_repository)]
PomodoroRepoDep = Annotated[PomodoroRepository, Depends(get_pomodoro_repository)]
TimerRepoDep = Annotated[TimerRepository, Depends(get_timer_repository)]
ClockDep = Annotated[Clock, Depends(get_clock)]

NOT_FOUND_ERROR = "La tarea no existe."


class CreateTaskRequest(BaseModel):
    """Request body for `POST /api/tasks`."""

    text: str
    tags: list[str] = []


class EditTaskTextRequest(BaseModel):
    """Request body for `PATCH /api/tasks/{task_id}/text`."""

    text: str


class EditTaskTagsRequest(BaseModel):
    """Request body for `PATCH /api/tasks/{task_id}/tags`: the full desired Tag set."""

    tags: list[str]


class ReorderTasksRequest(BaseModel):
    """Request body for `POST /api/tasks/reorder`: the full desired Active order."""

    task_ids: list[int]


class TaskCountsPublic(BaseModel):
    """Tab counts for the Active/Archived tabs."""

    active: int
    archived: int


class TaskPublic(BaseModel):
    """A Task as exposed over HTTP: Tags by name, plus the computed `deletable` flag."""

    id: int
    text: str
    position: int
    tags: list[str]
    created_at: datetime
    archived_at: datetime | None
    deletable: bool

    @classmethod
    def from_entity(cls, task: Task, *, tag_names: _TagNameIndex, deletable: bool) -> TaskPublic:
        """Build the public response shape from a `core` `Task` entity."""
        return cls(
            id=task.id,
            text=task.text,
            position=task.position,
            tags=tag_names.names_for(task.tag_ids),
            created_at=task.created_at,
            archived_at=task.archived_at,
            deletable=deletable,
        )


@dataclass(frozen=True)
class _TagNameIndex:
    """Lookup from `TagId` to name, built once per request from the User's Tag catalog."""

    by_id: dict[int, str]

    def names_for(self, tag_ids: tuple[TagId, ...]) -> list[str]:
        return [self.by_id[tag_id] for tag_id in tag_ids if tag_id in self.by_id]


def _tag_name_index(catalog: list[Tag]) -> _TagNameIndex:
    return _TagNameIndex({tag.id: tag.name for tag in catalog})


def _resolve_selected_tags(names: list[str], catalog: list[Tag]) -> list[TagId | str]:
    resolved: list[TagId | str] = []
    for name in names:
        if name == SIN_ETIQUETA:
            resolved.append(SIN_ETIQUETA)
            continue
        tag = find_tag_by_name(name, catalog)
        if tag is not None:
            resolved.append(tag.id)
    return resolved


def _resolve_or_create_tag_ids(
    names: list[str], user_id: UserId, tag_repo: TagRepository
) -> tuple[TagId, ...]:
    ids: list[TagId] = []
    seen: set[TagId] = set()
    for name in names:
        stripped = validate_tag_name(name)
        tag = tag_repo.get_or_create_by_name(user_id, stripped)
        if tag.id not in seen:
            seen.add(tag.id)
            ids.append(tag.id)
    return tuple(ids)


def _settled_in_progress_task_id(
    timer_repo: TimerRepository, pomodoro_repo: PomodoroRepository, user_id: UserId, now: datetime
) -> TaskId | None:
    """Return the Task id the User's settled Timer currently references, or `None` if Idle.

    Shares `api.timer`'s lazy settle-before-read rule via `core.timer.settle_and_persist`
    rather than trusting a possibly-stale stored Timer row.
    """
    return settle_and_persist(timer_repo, pomodoro_repo, user_id, now).task_id


def _is_deletable(
    pomodoro_repo: PomodoroRepository,
    user_id: UserId,
    task_id: TaskId,
    *,
    in_progress_task_id: TaskId | None,
) -> bool:
    if task_id == in_progress_task_id:
        return False
    return not pomodoro_repo.exists_for_task(user_id, task_id)


def _to_public(
    task: Task,
    *,
    tag_names: _TagNameIndex,
    pomodoro_repo: PomodoroRepository,
    in_progress_task_id: TaskId | None,
) -> TaskPublic:
    return TaskPublic.from_entity(
        task,
        tag_names=tag_names,
        deletable=_is_deletable(
            pomodoro_repo, task.user_id, task.id, in_progress_task_id=in_progress_task_id
        ),
    )


def _filtered_response(
    tasks: list[Task],
    *,
    text: str,
    tags: list[str],
    catalog: list[Tag],
    pomodoro_repo: PomodoroRepository,
    in_progress_task_id: TaskId | None,
) -> list[TaskPublic]:
    selected = _resolve_selected_tags(tags, catalog)
    filtered = filter_tasks(tasks, text, selected)
    tag_names = _tag_name_index(catalog)
    return [
        _to_public(
            task,
            tag_names=tag_names,
            pomodoro_repo=pomodoro_repo,
            in_progress_task_id=in_progress_task_id,
        )
        for task in filtered
    ]


@router.get("/active")
def list_active_tasks(
    user: UserDep,
    task_repo: TaskRepoDep,
    tag_repo: TagRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    timer_repo: TimerRepoDep,
    clock: ClockDep,
    tags: Annotated[list[str], Query(default_factory=list)],
    text: str = "",
) -> list[TaskPublic]:
    """Return the User's Active Tasks (newest first), filtered by `filter_tasks`."""
    active = sort_active_tasks(task_repo.list_active(user.id))
    catalog = tag_repo.list(user.id)
    in_progress_task_id = _settled_in_progress_task_id(
        timer_repo, pomodoro_repo, user.id, clock.now()
    )
    return _filtered_response(
        active,
        text=text,
        tags=tags,
        catalog=catalog,
        pomodoro_repo=pomodoro_repo,
        in_progress_task_id=in_progress_task_id,
    )


@router.get("/archived")
def list_archived_tasks(
    user: UserDep,
    task_repo: TaskRepoDep,
    tag_repo: TagRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    tags: Annotated[list[str], Query(default_factory=list)],
    text: str = "",
) -> list[TaskPublic]:
    """Return the User's Archived Tasks (most recently archived first), filtered.

    Never "in progress" (the Timer guard only applies to Active Tasks, and an
    Archived Task can't be started on in the first place), so no Timer lookup.
    """
    archived = sort_archived_tasks(task_repo.list_archived(user.id))
    catalog = tag_repo.list(user.id)
    return _filtered_response(
        archived,
        text=text,
        tags=tags,
        catalog=catalog,
        pomodoro_repo=pomodoro_repo,
        in_progress_task_id=None,
    )


@router.get("/summary")
def task_counts(user: UserDep, task_repo: TaskRepoDep) -> TaskCountsPublic:
    """Return the Active/Archived tab counts."""
    return TaskCountsPublic(
        active=len(task_repo.list_active(user.id)),
        archived=len(task_repo.list_archived(user.id)),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    body: CreateTaskRequest,
    user: UserDep,
    task_repo: TaskRepoDep,
    tag_repo: TagRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    clock: ClockDep,
) -> TaskPublic:
    """Create a new Active Task, assigning Tags by name (creating/reusing per T4)."""
    try:
        tag_ids = _resolve_or_create_tag_ids(body.tags, user.id, tag_repo)
    except TagNameEmptyError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    active_tasks = task_repo.list_active(user.id)
    try:
        draft = build_task(
            id=TaskId(0),
            user_id=user.id,
            text=body.text,
            active_tasks=active_tasks,
            created_at=clock.now(),
            tag_ids=tag_ids,
        )
    except DuplicateActiveTaskTextError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except (TaskTextEmptyError, TaskTextTooLongError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    stored = task_repo.add(draft)
    catalog = tag_repo.list(user.id)
    return _to_public(
        stored,
        tag_names=_tag_name_index(catalog),
        pomodoro_repo=pomodoro_repo,
        in_progress_task_id=None,
    )


def _get_owned_task(task_repo: TaskRepository, user: User, task_id: int) -> Task:
    task = task_repo.get(user.id, TaskId(task_id))
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_ERROR)
    return task


def _store_and_respond(
    task: Task,
    *,
    task_repo: TaskRepository,
    tag_repo: TagRepository,
    pomodoro_repo: PomodoroRepository,
    timer_repo: TimerRepository,
    user_id: UserId,
    now: datetime,
) -> TaskPublic:
    stored = task_repo.update(task)
    catalog = tag_repo.list(user_id)
    in_progress_task_id = _settled_in_progress_task_id(timer_repo, pomodoro_repo, user_id, now)
    return _to_public(
        stored,
        tag_names=_tag_name_index(catalog),
        pomodoro_repo=pomodoro_repo,
        in_progress_task_id=in_progress_task_id,
    )


@router.patch("/{task_id}/text")
def edit_text(
    task_id: int,
    body: EditTaskTextRequest,
    user: UserDep,
    task_repo: TaskRepoDep,
    tag_repo: TagRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    timer_repo: TimerRepoDep,
    clock: ClockDep,
) -> TaskPublic:
    """Edit a Task's text, applying the same validation `create` uses."""
    task = _get_owned_task(task_repo, user, task_id)
    active_tasks = task_repo.list_active(user.id)
    try:
        updated = edit_task_text(task, body.text, active_tasks)
    except DuplicateActiveTaskTextError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except (TaskTextEmptyError, TaskTextTooLongError) as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    return _store_and_respond(
        updated,
        task_repo=task_repo,
        tag_repo=tag_repo,
        pomodoro_repo=pomodoro_repo,
        timer_repo=timer_repo,
        user_id=user.id,
        now=clock.now(),
    )


@router.patch("/{task_id}/tags")
def edit_tags(
    task_id: int,
    body: EditTaskTagsRequest,
    user: UserDep,
    task_repo: TaskRepoDep,
    tag_repo: TagRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    timer_repo: TimerRepoDep,
    clock: ClockDep,
) -> TaskPublic:
    """Replace a Task's Tag assignments with the given set of names."""
    task = _get_owned_task(task_repo, user, task_id)
    try:
        tag_ids = _resolve_or_create_tag_ids(body.tags, user.id, tag_repo)
    except TagNameEmptyError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    return _store_and_respond(
        replace(task, tag_ids=tag_ids),
        task_repo=task_repo,
        tag_repo=tag_repo,
        pomodoro_repo=pomodoro_repo,
        timer_repo=timer_repo,
        user_id=user.id,
        now=clock.now(),
    )


@router.post("/reorder")
def reorder_tasks(
    body: ReorderTasksRequest,
    user: UserDep,
    task_repo: TaskRepoDep,
    tag_repo: TagRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    timer_repo: TimerRepoDep,
    clock: ClockDep,
) -> list[TaskPublic]:
    """Rewrite the User's Active Tasks' positions to match the given full order."""
    active_tasks = task_repo.list_active(user.id)
    ordered_ids = [TaskId(task_id) for task_id in body.task_ids]
    try:
        reordered = reorder_active_tasks(active_tasks, ordered_ids)
    except TaskReorderMismatchError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    stored = [task_repo.update(task) for task in sort_active_tasks(reordered)]
    catalog = tag_repo.list(user.id)
    tag_names = _tag_name_index(catalog)
    in_progress_task_id = _settled_in_progress_task_id(
        timer_repo, pomodoro_repo, user.id, clock.now()
    )
    return [
        _to_public(
            task,
            tag_names=tag_names,
            pomodoro_repo=pomodoro_repo,
            in_progress_task_id=in_progress_task_id,
        )
        for task in stored
    ]


@router.post("/{task_id}/archive")
def archive_task_route(
    task_id: int,
    user: UserDep,
    task_repo: TaskRepoDep,
    tag_repo: TagRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    timer_repo: TimerRepoDep,
    clock: ClockDep,
) -> TaskPublic:
    """Archive an Active Task, freezing its position.

    Rejected while the User's Timer is running/paused/pending-log/on-break on
    this Task (user story #31): see `ensure_task_not_in_progress`.
    """
    task = _get_owned_task(task_repo, user, task_id)
    now = clock.now()
    in_progress_task_id = _settled_in_progress_task_id(timer_repo, pomodoro_repo, user.id, now)
    try:
        archived = archive_task(task, now, in_progress=task.id == in_progress_task_id)
    except TaskInProgressError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    stored = task_repo.update(archived)
    catalog = tag_repo.list(user.id)
    return _to_public(
        stored,
        tag_names=_tag_name_index(catalog),
        pomodoro_repo=pomodoro_repo,
        in_progress_task_id=in_progress_task_id,
    )


@router.post("/{task_id}/unarchive")
def unarchive_task_route(
    task_id: int,
    user: UserDep,
    task_repo: TaskRepoDep,
    tag_repo: TagRepoDep,
    pomodoro_repo: PomodoroRepoDep,
) -> TaskPublic:
    """Unarchive a Task, sending it to the end of the Active list.

    An Archived Task is never the one the Timer references (starting a
    Pomodoro requires an Active Task), so no Timer lookup is needed here.
    """
    task = _get_owned_task(task_repo, user, task_id)
    active_tasks = task_repo.list_active(user.id)
    try:
        unarchived = unarchive_task(task, active_tasks)
    except UnarchiveCollisionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    stored = task_repo.update(unarchived)
    catalog = tag_repo.list(user.id)
    return _to_public(
        stored,
        tag_names=_tag_name_index(catalog),
        pomodoro_repo=pomodoro_repo,
        in_progress_task_id=None,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    user: UserDep,
    task_repo: TaskRepoDep,
    pomodoro_repo: PomodoroRepoDep,
    timer_repo: TimerRepoDep,
    clock: ClockDep,
) -> None:
    """Permanently delete a Task, only if it has zero Pomodoros and isn't in progress."""
    task = _get_owned_task(task_repo, user, task_id)
    has_pomodoros = pomodoro_repo.exists_for_task(user.id, task.id)
    in_progress_task_id = _settled_in_progress_task_id(
        timer_repo, pomodoro_repo, user.id, clock.now()
    )
    try:
        ensure_task_deletable(
            has_pomodoros=has_pomodoros, in_progress=task.id == in_progress_task_id
        )
    except TaskInProgressError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except TaskHasPomodorosError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    task_repo.delete(user.id, task.id)
