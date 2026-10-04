"""The single `filter_tasks` contract shared by Active/Archived/History views.

Pure core: no FastAPI/SQLModel/Pydantic imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pomodoro.core.normalization import normalize_key

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pomodoro.core.entities import TagId, Task

SIN_ETIQUETA = "sin etiqueta"
"""Sentinel value for `selected_tags`: matches Tasks with zero Tags."""


def filter_tasks(
    tasks: Sequence[Task],
    name_query: str,
    selected_tags: Sequence[TagId | str],
) -> list[Task]:
    """Filter `tasks` by a case-insensitive text substring AND a tag selection.

    `name_query` matches as a substring of the Task's text, case-insensitively;
    an empty query imposes no restriction. `selected_tags` matches if the Task
    carries any one of the given tag ids (OR), or if `SIN_ETIQUETA` is among
    them and the Task has zero Tags; an empty selection imposes no restriction.
    The two filters combine with AND.
    """
    query_key = normalize_key(name_query)
    wants_untagged = SIN_ETIQUETA in selected_tags
    tag_ids = {tag for tag in selected_tags if tag != SIN_ETIQUETA}

    def matches_text(task: Task) -> bool:
        return not query_key or query_key in normalize_key(task.text)

    def matches_tags(task: Task) -> bool:
        if not selected_tags:
            return True
        if wants_untagged and not task.tag_ids:
            return True
        return any(tag_id in task.tag_ids for tag_id in tag_ids)

    return [task for task in tasks if matches_text(task) and matches_tags(task)]
