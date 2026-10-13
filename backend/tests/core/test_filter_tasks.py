"""Unit tests for the pure Task filtering contract (User Stories 40-45)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pomodoro.core.tags import TagId
from pomodoro.core.task_filtering import NO_TAG_SENTINEL, filter_tasks
from pomodoro.core.tasks import Task, TaskId
from pomodoro.core.users import UserId

pytestmark = pytest.mark.unit

USER_ID = UserId(UUID(int=1))
WORK_TAG_ID = TagId(UUID(int=2))
PERSONAL_TAG_ID = TagId(UUID(int=3))


def _task(number: int, text: str, tag_ids: tuple[TagId, ...] = ()) -> Task:
    return Task(
        id=TaskId(UUID(int=number)),
        user_id=USER_ID,
        text=text,
        position=number,
        tag_ids=tag_ids,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        archived_at=None,
    )


def test_filter_tasks_matches_a_case_insensitive_text_substring() -> None:
    tasks = [_task(10, "Write report"), _task(11, "Review pull request")]

    filtered = filter_tasks(tasks, name_query="REPORT", selected_tags=())

    assert [task.text for task in filtered] == ["Write report"]


def test_filter_tasks_ors_the_selected_tags() -> None:
    work_task = _task(10, "Write report", (WORK_TAG_ID,))
    personal_task = _task(11, "Plan weekend", (PERSONAL_TAG_ID,))
    untagged_task = _task(12, "Read book")

    filtered = filter_tasks(
        [work_task, personal_task, untagged_task],
        name_query=None,
        selected_tags=(WORK_TAG_ID, PERSONAL_TAG_ID),
    )

    assert [task.id for task in filtered] == [work_task.id, personal_task.id]


def test_filter_tasks_combines_the_no_tag_sentinel_with_other_tags() -> None:
    work_task = _task(10, "Write report", (WORK_TAG_ID,))
    untagged_task = _task(11, "Read book")
    personal_task = _task(12, "Plan weekend", (PERSONAL_TAG_ID,))

    filtered = filter_tasks(
        [work_task, untagged_task, personal_task],
        name_query=None,
        selected_tags=(WORK_TAG_ID, NO_TAG_SENTINEL),
    )

    assert [task.id for task in filtered] == [work_task.id, untagged_task.id]


def test_filter_tasks_ands_text_and_tag_filters_and_leaves_empty_filters_unrestricted() -> None:
    report_task = _task(10, "Write report", (WORK_TAG_ID,))
    review_task = _task(11, "Review report", (PERSONAL_TAG_ID,))
    untagged_task = _task(12, "Read book")
    tasks = [report_task, review_task, untagged_task]

    filtered = filter_tasks(tasks, name_query="report", selected_tags=(WORK_TAG_ID,))

    assert [task.id for task in filtered] == [report_task.id]
    assert filter_tasks(tasks, name_query="", selected_tags=()) == tasks
