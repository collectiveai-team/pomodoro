"""Pure, shared filtering rules for Task lists (User Stories 40-45)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pomodoro.core.tags import TagId

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from pomodoro.core.tasks import Task

NO_TAG_SENTINEL = "sin etiqueta"
type TaskTagFilter = TagId | Literal["sin etiqueta"]


def filter_tasks(
    tasks: Iterable[Task], name_query: str | None, selected_tags: Collection[TaskTagFilter]
) -> list[Task]:
    """Return Tasks matching the text and Tag filters, preserving their incoming order.

    Text matching is case-insensitive substring matching. Selected Tags are alternatives, with
    ``"sin etiqueta"`` representing untagged Tasks; text and Tag filters combine with AND.
    """
    query = name_query.casefold() if name_query else None
    return [
        task
        for task in tasks
        if _matches_text(task, query) and _matches_selected_tags(task, selected_tags)
    ]


def _matches_text(task: Task, query: str | None) -> bool:
    return query is None or query in task.text.casefold()


def _matches_selected_tags(task: Task, selected_tags: Collection[TaskTagFilter]) -> bool:
    if not selected_tags:
        return True
    if not task.tag_ids:
        return NO_TAG_SENTINEL in selected_tags
    return bool(set(task.tag_ids) & set(selected_tags))
