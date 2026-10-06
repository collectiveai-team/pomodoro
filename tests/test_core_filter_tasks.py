"""Unit tests for the shared `filter_tasks` contract."""

from __future__ import annotations

from datetime import UTC, datetime

from pomodoro.core.entities import TagId, Task, TaskId, UserId
from pomodoro.core.filtering import SIN_ETIQUETA, filter_tasks

USER = UserId(1)
NOW = datetime(2026, 1, 1, tzinfo=UTC)

WORK = TagId(1)
URGENT = TagId(2)


def make_task(*, id: int, text: str, tag_ids: tuple[TagId, ...] = ()) -> Task:
    return Task(
        id=TaskId(id),
        user_id=USER,
        text=text,
        position=0,
        tag_ids=tag_ids,
        created_at=NOW,
        archived_at=None,
    )


def test_empty_query_and_empty_selection_imposes_no_restriction() -> None:
    tasks = [make_task(id=1, text="Informe"), make_task(id=2, text="Reunión", tag_ids=(WORK,))]
    assert filter_tasks(tasks, "", []) == tasks


def test_text_filter_is_case_insensitive_substring_match() -> None:
    tasks = [make_task(id=1, text="Escribir Informe"), make_task(id=2, text="Otra cosa")]
    result = filter_tasks(tasks, "INFORME", [])
    assert [t.id for t in result] == [TaskId(1)]


def test_text_filter_matches_substring_anywhere_in_text() -> None:
    tasks = [make_task(id=1, text="Preparar informe mensual")]
    assert filter_tasks(tasks, "orme men", []) == tasks


def test_tag_filter_ors_among_selected_tags() -> None:
    work_task = make_task(id=1, text="A", tag_ids=(WORK,))
    urgent_task = make_task(id=2, text="B", tag_ids=(URGENT,))
    neither_task = make_task(id=3, text="C")
    result = filter_tasks([work_task, urgent_task, neither_task], "", [WORK, URGENT])
    assert {t.id for t in result} == {work_task.id, urgent_task.id}


def test_sin_etiqueta_matches_only_tasks_with_zero_tags() -> None:
    tagged = make_task(id=1, text="A", tag_ids=(WORK,))
    untagged = make_task(id=2, text="B")
    result = filter_tasks([tagged, untagged], "", [SIN_ETIQUETA])
    assert [t.id for t in result] == [untagged.id]


def test_sin_etiqueta_combines_with_other_selected_tags_via_or() -> None:
    tagged = make_task(id=1, text="A", tag_ids=(WORK,))
    other_tagged = make_task(id=2, text="B", tag_ids=(URGENT,))
    untagged = make_task(id=3, text="C")
    result = filter_tasks([tagged, other_tagged, untagged], "", [SIN_ETIQUETA, WORK])
    assert {t.id for t in result} == {tagged.id, untagged.id}


def test_text_and_tag_filters_combine_with_and() -> None:
    matches_both = make_task(id=1, text="Informe final", tag_ids=(WORK,))
    matches_text_only = make_task(id=2, text="Informe borrador")
    matches_tag_only = make_task(id=3, text="Otra cosa", tag_ids=(WORK,))
    result = filter_tasks([matches_both, matches_text_only, matches_tag_only], "informe", [WORK])
    assert [t.id for t in result] == [matches_both.id]


def test_sin_etiqueta_and_text_query_combine_with_and() -> None:
    matches_both = make_task(id=1, text="Informe urgente")
    untagged_no_text_match = make_task(id=2, text="Otra cosa")
    tagged_text_match = make_task(id=3, text="Informe tagged", tag_ids=(WORK,))
    result = filter_tasks(
        [matches_both, untagged_no_text_match, tagged_text_match],
        "informe",
        [SIN_ETIQUETA],
    )
    assert [t.id for t in result] == [matches_both.id]


def test_tag_filter_excludes_tasks_with_no_matching_tag() -> None:
    tasks = [make_task(id=1, text="A", tag_ids=(WORK,))]
    assert filter_tasks(tasks, "", [URGENT]) == []
