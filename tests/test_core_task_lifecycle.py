"""Unit tests for Task lifecycle rules and the TaskRepository Protocol."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pomodoro.core.entities import Task, TaskId, UserId
from pomodoro.core.errors import (
    DuplicateActiveTaskTextError,
    TaskHasPomodorosError,
    TaskReorderMismatchError,
    TaskTextEmptyError,
    TaskTextTooLongError,
    UnarchiveCollisionError,
)
from pomodoro.core.repositories import TaskRepository
from pomodoro.core.tasks import (
    archive_task,
    compute_create_position,
    create_task,
    edit_task_text,
    ensure_task_deletable,
    reorder_active_tasks,
    sort_active_tasks,
    sort_archived_tasks,
    unarchive_task,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
LATER = datetime(2026, 1, 2, tzinfo=UTC)
USER = UserId(1)


def make_task(
    *,
    id: int = 1,
    text: str = "Task",
    position: int = 0,
    archived_at: datetime | None = None,
) -> Task:
    return Task(
        id=TaskId(id),
        user_id=USER,
        text=text,
        position=position,
        tag_ids=(),
        created_at=NOW,
        archived_at=archived_at,
    )


# --- create_task -----------------------------------------------------------


def test_create_task_gets_minimum_position_minus_one_and_sorts_first() -> None:
    existing = [make_task(id=1, text="Existing", position=3)]
    new_task = create_task(
        id=TaskId(2), user_id=USER, text="New", active_tasks=existing, created_at=NOW
    )
    assert new_task.position == 2
    ordered = sort_active_tasks([*existing, new_task])
    assert ordered[0].id == new_task.id


def test_create_task_position_allows_negatives() -> None:
    existing = [make_task(id=1, text="Existing", position=-5)]
    new_task = create_task(
        id=TaskId(2), user_id=USER, text="New", active_tasks=existing, created_at=NOW
    )
    assert new_task.position == -6


def test_create_task_with_no_active_tasks_starts_at_zero() -> None:
    assert compute_create_position([]) == 0
    new_task = create_task(
        id=TaskId(1), user_id=USER, text="First", active_tasks=[], created_at=NOW
    )
    assert new_task.position == 0


def test_create_task_rejects_empty_text_after_stripping() -> None:
    with pytest.raises(TaskTextEmptyError):
        create_task(id=TaskId(1), user_id=USER, text="   ", active_tasks=[], created_at=NOW)


def test_create_task_rejects_text_over_200_chars() -> None:
    with pytest.raises(TaskTextTooLongError):
        create_task(id=TaskId(1), user_id=USER, text="x" * 201, active_tasks=[], created_at=NOW)


def test_create_task_allows_exactly_200_chars() -> None:
    task = create_task(id=TaskId(1), user_id=USER, text="x" * 200, active_tasks=[], created_at=NOW)
    assert task.text == "x" * 200


def test_create_task_rejects_duplicate_among_active_tasks_normalized() -> None:
    existing = [make_task(id=1, text=" Informe ")]
    with pytest.raises(DuplicateActiveTaskTextError):
        create_task(
            id=TaskId(2), user_id=USER, text="informe", active_tasks=existing, created_at=NOW
        )


def test_create_task_allows_text_matching_an_archived_task() -> None:
    archived = [make_task(id=1, text="Informe", archived_at=NOW)]
    task = create_task(id=TaskId(2), user_id=USER, text="Informe", active_tasks=[], created_at=NOW)
    assert task.text == "Informe"
    assert archived[0].archived_at is not None


# --- edit_task_text ----------------------------------------------------------


def test_edit_task_text_applies_the_same_validation_as_create() -> None:
    task = make_task(id=1, text="Old")
    with pytest.raises(TaskTextEmptyError):
        edit_task_text(task, "   ", active_tasks=[task])
    with pytest.raises(TaskTextTooLongError):
        edit_task_text(task, "x" * 201, active_tasks=[task])


def test_edit_task_text_rejects_duplicate_with_another_active_task() -> None:
    other = make_task(id=2, text="Other")
    task = make_task(id=1, text="Mine")
    with pytest.raises(DuplicateActiveTaskTextError):
        edit_task_text(task, "other", active_tasks=[task, other])


def test_edit_task_text_allows_keeping_its_own_unchanged_text() -> None:
    task = make_task(id=1, text="Mine")
    edited = edit_task_text(task, "Mine", active_tasks=[task])
    assert edited.text == "Mine"


def test_edit_archived_task_text_does_not_check_duplicates() -> None:
    active = make_task(id=1, text="Shared")
    archived = make_task(id=2, text="Archived", archived_at=NOW)
    edited = edit_task_text(archived, "Shared", active_tasks=[active])
    assert edited.text == "Shared"


# --- archive / unarchive -----------------------------------------------------


def test_archive_task_freezes_position_and_sets_archived_at() -> None:
    task = make_task(id=1, text="Task", position=5)
    archived = archive_task(task, archived_at=LATER)
    assert archived.position == 5
    assert archived.archived_at == LATER


def test_unarchive_task_clears_archived_at_and_moves_to_end() -> None:
    task = make_task(id=1, text="Task", position=2, archived_at=NOW)
    active_tasks = [make_task(id=2, text="Other", position=7)]
    unarchived = unarchive_task(task, active_tasks=active_tasks)
    assert unarchived.archived_at is None
    assert unarchived.position == 8


def test_unarchive_task_with_no_active_tasks_goes_to_zero() -> None:
    task = make_task(id=1, text="Task", position=2, archived_at=NOW)
    unarchived = unarchive_task(task, active_tasks=[])
    assert unarchived.position == 0


def test_unarchive_task_rejects_collision_with_active_task_text() -> None:
    task = make_task(id=1, text="Informe", archived_at=NOW)
    active_tasks = [make_task(id=2, text=" informe ", position=0)]
    with pytest.raises(UnarchiveCollisionError):
        unarchive_task(task, active_tasks=active_tasks)


def test_create_then_archive_then_create_same_text_is_allowed() -> None:
    """Archived/active text-collision asymmetry: archiving frees the text up."""
    original = make_task(id=1, text="Informe", position=0)
    archived = archive_task(original, archived_at=NOW)
    recreated = create_task(
        id=TaskId(2), user_id=USER, text="Informe", active_tasks=[], created_at=LATER
    )
    assert archived.text == recreated.text
    assert archived.archived_at is not None
    assert recreated.archived_at is None


# --- reorder ------------------------------------------------------------------


def test_reorder_active_tasks_rewrites_positions_0_to_n_minus_1() -> None:
    tasks = [
        make_task(id=1, position=10),
        make_task(id=2, position=20),
        make_task(id=3, position=5),
    ]
    reordered = reorder_active_tasks(tasks, ordered_ids=[TaskId(3), TaskId(1), TaskId(2)])
    by_id = {task.id: task.position for task in reordered}
    assert by_id == {TaskId(3): 0, TaskId(1): 1, TaskId(2): 2}


def test_reorder_active_tasks_rejects_a_mismatched_id_list() -> None:
    tasks = [make_task(id=1), make_task(id=2)]
    with pytest.raises(TaskReorderMismatchError):
        reorder_active_tasks(tasks, ordered_ids=[TaskId(1)])
    with pytest.raises(TaskReorderMismatchError):
        reorder_active_tasks(tasks, ordered_ids=[TaskId(1), TaskId(2), TaskId(3)])
    with pytest.raises(TaskReorderMismatchError):
        reorder_active_tasks(tasks, ordered_ids=[TaskId(1), TaskId(1)])


# --- sorting ------------------------------------------------------------------


def test_sort_active_tasks_by_position_then_id() -> None:
    a = make_task(id=2, position=0)
    b = make_task(id=1, position=0)
    c = make_task(id=3, position=-1)
    assert [task.id for task in sort_active_tasks([a, b, c])] == [TaskId(3), TaskId(1), TaskId(2)]


def test_sort_archived_tasks_by_archived_at_descending() -> None:
    earlier = make_task(id=1, archived_at=NOW)
    later = make_task(id=2, archived_at=LATER)
    assert [task.id for task in sort_archived_tasks([earlier, later])] == [
        TaskId(2),
        TaskId(1),
    ]


# --- delete --------------------------------------------------------------------


def test_ensure_task_deletable_allows_a_task_with_zero_pomodoros() -> None:
    ensure_task_deletable(has_pomodoros=False)


def test_ensure_task_deletable_rejects_a_task_with_any_pomodoro() -> None:
    with pytest.raises(TaskHasPomodorosError):
        ensure_task_deletable(has_pomodoros=True)


# --- TaskRepository Protocol ----------------------------------------------------


class FakeTaskRepository:
    """In-memory TaskRepository used only to confirm the Protocol's shape."""

    def __init__(self) -> None:
        self._tasks: dict[TaskId, Task] = {}
        self._next_id = 1

    def list_active(self, user_id: UserId) -> list[Task]:
        return [t for t in self._tasks.values() if t.user_id == user_id and t.archived_at is None]

    def list_archived(self, user_id: UserId) -> list[Task]:
        return [
            t for t in self._tasks.values() if t.user_id == user_id and t.archived_at is not None
        ]

    def get(self, user_id: UserId, task_id: TaskId) -> Task | None:
        task = self._tasks.get(task_id)
        return task if task is not None and task.user_id == user_id else None

    def add(self, task: Task) -> Task:
        persisted = replace(task, id=TaskId(self._next_id))
        self._next_id += 1
        self._tasks[persisted.id] = persisted
        return persisted

    def update(self, task: Task) -> Task:
        self._tasks[task.id] = task
        return task

    def delete(self, user_id: UserId, task_id: TaskId) -> None:
        existing = self.get(user_id, task_id)
        if existing is not None:
            del self._tasks[task_id]


def test_fake_task_repository_satisfies_the_protocol() -> None:
    repo: TaskRepository = FakeTaskRepository()
    assert isinstance(repo, TaskRepository)

    draft = make_task(id=0, text="Persisted")
    persisted = repo.add(draft)
    assert persisted.id != draft.id

    assert repo.get(USER, persisted.id) == persisted
    assert repo.list_active(USER) == [persisted]
    assert repo.list_archived(USER) == []

    archived = archive_task(persisted, archived_at=NOW)
    repo.update(archived)
    assert repo.list_archived(USER) == [archived]
    assert repo.list_active(USER) == []

    repo.delete(USER, archived.id)
    assert repo.get(USER, archived.id) is None
