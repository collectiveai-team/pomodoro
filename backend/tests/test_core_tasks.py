"""Tests for the Task lifecycle rules in core/ (T4)."""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

import pytest

from pomodoro.core.entities import Task, TaskId, UserId
from pomodoro.core.errors import (
    DuplicateTaskTextError,
    TaskHasPomodorosError,
    TaskTextEmptyError,
    TaskTextTooLongError,
    TaskUnarchiveCollisionError,
)
from pomodoro.core.tasks import (
    MAX_TASK_TEXT_LENGTH,
    archive_task,
    create_task,
    edit_task_text,
    ensure_task_deletable,
    order_active_tasks,
    order_archived_tasks,
    reorder_active_tasks,
    unarchive_task,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_USER = UserId(1)


def _task(
    *,
    id: int = 1,
    text: str = "x",
    position: int = 0,
    archived_at: datetime | None = None,
) -> Task:
    return Task(
        id=TaskId(id),
        user_id=_USER,
        text=text,
        position=position,
        created_at=_NOW,
        archived_at=archived_at,
    )


class TestTaskHasNoOwnCounters:
    def test_task_entity_declares_no_counter_fields(self) -> None:
        field_names = {f.name for f in fields(Task)}
        assert field_names == {
            "id",
            "user_id",
            "text",
            "position",
            "created_at",
            "archived_at",
            "tag_ids",
        }


class TestCreateTask:
    def test_first_task_for_a_user_gets_position_minus_one(self) -> None:
        task = create_task(
            [],
            new_task_id=TaskId(1),
            user_id=_USER,
            text="Write the report",
            created_at=_NOW,
        )
        assert task.position == -1
        assert task.text == "Write the report"

    def test_new_task_goes_before_the_lowest_active_position(self) -> None:
        existing = [_task(id=1, position=-3), _task(id=2, position=0)]
        task = create_task(
            existing, new_task_id=TaskId(3), user_id=_USER, text="y", created_at=_NOW
        )
        assert task.position == -4

    def test_archived_tasks_do_not_affect_the_new_position(self) -> None:
        existing = [_task(id=1, position=-100, archived_at=_NOW)]
        task = create_task(
            existing, new_task_id=TaskId(2), user_id=_USER, text="y", created_at=_NOW
        )
        assert task.position == -1

    def test_empty_text_is_rejected(self) -> None:
        with pytest.raises(TaskTextEmptyError):
            create_task([], new_task_id=TaskId(1), user_id=_USER, text="   ", created_at=_NOW)

    def test_text_over_200_characters_is_rejected(self) -> None:
        with pytest.raises(TaskTextTooLongError):
            create_task(
                [],
                new_task_id=TaskId(1),
                user_id=_USER,
                text="x" * (MAX_TASK_TEXT_LENGTH + 1),
                created_at=_NOW,
            )

    def test_text_at_the_200_character_limit_is_accepted(self) -> None:
        task = create_task(
            [],
            new_task_id=TaskId(1),
            user_id=_USER,
            text="x" * MAX_TASK_TEXT_LENGTH,
            created_at=_NOW,
        )
        assert len(task.text) == MAX_TASK_TEXT_LENGTH

    def test_duplicate_text_among_active_tasks_is_rejected_case_and_space_insensitive(self) -> None:
        existing = [_task(id=1, text="Trabajo")]
        with pytest.raises(DuplicateTaskTextError):
            create_task(
                existing,
                new_task_id=TaskId(2),
                user_id=_USER,
                text=" TRABAJO ",
                created_at=_NOW,
            )

    def test_same_text_as_an_archived_task_is_allowed(self) -> None:
        existing = [_task(id=1, text="Trabajo", archived_at=_NOW)]
        task = create_task(
            existing, new_task_id=TaskId(2), user_id=_USER, text="Trabajo", created_at=_NOW
        )
        assert task.text == "Trabajo"


class TestEditTaskText:
    def test_edit_changes_the_text(self) -> None:
        task = _task(id=1, text="old")
        updated = edit_task_text([task], task, text="new")
        assert updated.text == "new"
        assert updated.id == task.id

    def test_edit_rejects_empty_text(self) -> None:
        task = _task(id=1, text="old")
        with pytest.raises(TaskTextEmptyError):
            edit_task_text([task], task, text="   ")

    def test_edit_rejects_collision_with_another_active_task(self) -> None:
        other = _task(id=1, text="Trabajo")
        task = _task(id=2, text="Other")
        with pytest.raises(DuplicateTaskTextError):
            edit_task_text([other, task], task, text="trabajo")

    def test_edit_allows_keeping_the_tasks_own_current_text(self) -> None:
        task = _task(id=1, text="Trabajo")
        updated = edit_task_text([task], task, text="Trabajo")
        assert updated.text == "Trabajo"

    def test_editing_an_archived_task_does_not_check_active_collisions(self) -> None:
        active = _task(id=1, text="Trabajo")
        archived = _task(id=2, text="Other", archived_at=_NOW)
        updated = edit_task_text([active, archived], archived, text="Trabajo")
        assert updated.text == "Trabajo"
        assert updated.archived_at == _NOW


class TestArchiveTask:
    def test_archive_sets_archived_at_and_freezes_position(self) -> None:
        task = _task(id=1, position=5)
        archived = archive_task(task, archived_at=_NOW)
        assert archived.archived_at == _NOW
        assert archived.position == 5


class TestUnarchiveTask:
    def test_unarchive_clears_archived_at_and_goes_to_the_end(self) -> None:
        archived = _task(id=1, text="a", position=5, archived_at=_NOW)
        other_active = _task(id=2, text="b", position=3)
        unarchived = unarchive_task([archived, other_active], archived)
        assert unarchived.archived_at is None
        assert unarchived.position == 4

    def test_unarchive_into_an_empty_active_list_gets_position_zero(self) -> None:
        archived = _task(id=1, position=5, archived_at=_NOW)
        unarchived = unarchive_task([archived], archived)
        assert unarchived.position == 0

    def test_unarchive_collision_with_an_active_task_is_rejected(self) -> None:
        archived = _task(id=1, text="Trabajo", archived_at=_NOW)
        active = _task(id=2, text="trabajo")
        with pytest.raises(TaskUnarchiveCollisionError):
            unarchive_task([archived, active], archived)


class TestReorderActiveTasks:
    def test_reorder_rewrites_positions_to_0_through_n_minus_1(self) -> None:
        a = _task(id=1, position=-5)
        b = _task(id=2, position=10)
        c = _task(id=3, position=0)
        reordered = reorder_active_tasks([a, b, c], [TaskId(2), TaskId(3), TaskId(1)])
        positions = {task.id: task.position for task in reordered}
        assert positions == {TaskId(2): 0, TaskId(3): 1, TaskId(1): 2}

    def test_reorder_is_stable_across_repeated_calls_with_the_same_order(self) -> None:
        a = _task(id=1, position=-5)
        b = _task(id=2, position=10)
        first = reorder_active_tasks([a, b], [TaskId(1), TaskId(2)])
        second = reorder_active_tasks(first, [TaskId(1), TaskId(2)])
        assert [task.position for task in second] == [0, 1]

    def test_reorder_rejects_a_list_that_does_not_match_the_active_set(self) -> None:
        a = _task(id=1)
        b = _task(id=2)
        with pytest.raises(ValueError, match="ordered_ids"):
            reorder_active_tasks([a, b], [TaskId(1)])


class TestDeleteTask:
    def test_task_without_pomodoros_is_deletable(self) -> None:
        assert ensure_task_deletable(_task(id=1), has_pomodoros=False) is None

    def test_task_with_a_pomodoro_is_not_deletable(self) -> None:
        with pytest.raises(TaskHasPomodorosError):
            ensure_task_deletable(_task(id=1), has_pomodoros=True)


class TestOrdering:
    def test_active_tasks_are_ordered_by_position_then_id(self) -> None:
        a = _task(id=2, position=0)
        b = _task(id=1, position=0)
        c = _task(id=3, position=-1)
        assert [task.id for task in order_active_tasks([a, b, c])] == [
            TaskId(3),
            TaskId(1),
            TaskId(2),
        ]

    def test_archived_tasks_exclude_active_ones(self) -> None:
        active = _task(id=1)
        archived = _task(id=2, archived_at=_NOW)
        assert order_active_tasks([active, archived]) == [active]
        assert order_archived_tasks([active, archived]) == [archived]

    def test_archived_tasks_are_ordered_by_archived_at_descending(self) -> None:
        earlier = _task(id=1, archived_at=datetime(2026, 1, 1, tzinfo=UTC))
        later = _task(id=2, archived_at=datetime(2026, 1, 2, tzinfo=UTC))
        assert [task.id for task in order_archived_tasks([earlier, later])] == [
            TaskId(2),
            TaskId(1),
        ]

    def test_negative_positions_are_valid_and_order_correctly(self) -> None:
        a = _task(id=1, position=-10)
        b = _task(id=2, position=-1)
        assert [task.id for task in order_active_tasks([b, a])] == [TaskId(1), TaskId(2)]
