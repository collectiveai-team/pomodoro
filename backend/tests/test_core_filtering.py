"""Tests for the shared `filter_tasks` contract in core/ (T5, spec stories 40-44)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pomodoro.core.entities import TagId, Task, TaskId, UserId
from pomodoro.core.filtering import NO_TAG, filter_tasks

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_USER = UserId(1)
_WORK = TagId(1)
_HOME = TagId(2)
_UNKNOWN = TagId(999)


def _task(*, id: int, text: str, tag_ids: frozenset[TagId] = frozenset()) -> Task:
    return Task(
        id=TaskId(id),
        user_id=_USER,
        text=text,
        position=0,
        created_at=_NOW,
        tag_ids=tag_ids,
    )


class TestEmptyFilterIsUnrestricted:
    def test_no_query_and_no_selected_tags_returns_every_task(self) -> None:
        tasks = [_task(id=1, text="Write the report"), _task(id=2, text="Buy milk")]
        assert filter_tasks(tasks, "", []) == tasks


class TestTextFilter:
    def test_substring_match_is_case_insensitive(self) -> None:
        tasks = [_task(id=1, text="Write the Report"), _task(id=2, text="Buy milk")]
        assert filter_tasks(tasks, "report", []) == [tasks[0]]

    def test_substring_match_ignores_surrounding_whitespace_in_the_query(self) -> None:
        tasks = [_task(id=1, text="Write the report")]
        assert filter_tasks(tasks, "  REPORT  ", []) == tasks

    def test_no_match_returns_empty(self) -> None:
        tasks = [_task(id=1, text="Write the report")]
        assert filter_tasks(tasks, "nonexistent", []) == []


class TestTagFilterIsOr:
    def test_selecting_one_tag_returns_tasks_carrying_it(self) -> None:
        work_task = _task(id=1, text="a", tag_ids=frozenset({_WORK}))
        home_task = _task(id=2, text="b", tag_ids=frozenset({_HOME}))
        assert filter_tasks([work_task, home_task], "", [_WORK]) == [work_task]

    def test_selecting_two_tags_returns_tasks_carrying_either(self) -> None:
        work_task = _task(id=1, text="a", tag_ids=frozenset({_WORK}))
        home_task = _task(id=2, text="b", tag_ids=frozenset({_HOME}))
        neither_task = _task(id=3, text="c", tag_ids=frozenset())
        result = filter_tasks([work_task, home_task, neither_task], "", [_WORK, _HOME])
        assert result == [work_task, home_task]

    def test_unknown_tag_id_returns_empty_not_the_full_list(self) -> None:
        """Regression guard: an unmatched Tag id must narrow to empty, never widen."""
        tasks = [
            _task(id=1, text="a", tag_ids=frozenset({_WORK})),
            _task(id=2, text="b", tag_ids=frozenset()),
        ]
        assert filter_tasks(tasks, "", [_UNKNOWN]) == []


class TestNoTagSpecialMember:
    def test_no_tag_matches_only_untagged_tasks(self) -> None:
        tagged = _task(id=1, text="a", tag_ids=frozenset({_WORK}))
        untagged = _task(id=2, text="b", tag_ids=frozenset())
        assert filter_tasks([tagged, untagged], "", [NO_TAG]) == [untagged]

    def test_no_tag_is_combinable_with_real_tag_chips(self) -> None:
        work_task = _task(id=1, text="a", tag_ids=frozenset({_WORK}))
        home_task = _task(id=2, text="b", tag_ids=frozenset({_HOME}))
        untagged = _task(id=3, text="c", tag_ids=frozenset())
        result = filter_tasks([work_task, home_task, untagged], "", [NO_TAG, _WORK])
        assert result == [work_task, untagged]


class TestTextAndTagsCombineWithAnd:
    def test_a_task_must_match_both_filters_to_be_included(self) -> None:
        matches_both = _task(id=1, text="Write the report", tag_ids=frozenset({_WORK}))
        matches_text_only = _task(id=2, text="Write the memo", tag_ids=frozenset({_HOME}))
        matches_tag_only = _task(id=3, text="Buy milk", tag_ids=frozenset({_WORK}))
        result = filter_tasks([matches_both, matches_text_only, matches_tag_only], "write", [_WORK])
        assert result == [matches_both]

    def test_no_tag_still_combines_with_the_text_filter(self) -> None:
        matches_both = _task(id=1, text="Write the report", tag_ids=frozenset())
        wrong_text = _task(id=2, text="Buy milk", tag_ids=frozenset())
        tagged = _task(id=3, text="Write the memo", tag_ids=frozenset({_WORK}))
        result = filter_tasks([matches_both, wrong_text, tagged], "write", [NO_TAG])
        assert result == [matches_both]
