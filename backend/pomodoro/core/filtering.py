"""The single `filter_tasks` contract shared by Active/Archived/History (T5).

Combines a case-insensitive text substring filter with an OR-of-Tags filter via
AND; `NO_TAG` is a special member of `selected_tags` that matches Tasks with no
Tag at all, combinable with real Tag ids. An empty query and empty selection
leave the list unrestricted. A selected Tag id that matches no Task (e.g. one
that doesn't exist for the User) correctly narrows the result to empty — it
must never fall back to the unrestricted list (regression guard, issue #12).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pomodoro.core.normalization import normalize

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from pomodoro.core.entities import TagId, Task


class _NoTagSentinel:
    """The 'sin etiqueta' special member of `selected_tags`."""

    def __repr__(self) -> str:
        return "NO_TAG"


NO_TAG: Final = _NoTagSentinel()


def filter_tasks(
    tasks: Sequence[Task],
    name_query: str,
    selected_tags: Collection[TagId | _NoTagSentinel],
) -> list[Task]:
    """Return `tasks` matching `name_query` (substring) AND `selected_tags` (OR)."""
    query_key = normalize(name_query)
    by_name = [task for task in tasks if not query_key or query_key in normalize(task.text)]
    if not selected_tags:
        return by_name
    real_tag_ids = {tag_id for tag_id in selected_tags if tag_id is not NO_TAG}
    return [
        task
        for task in by_name
        if (NO_TAG in selected_tags and not task.tag_ids) or task.tag_ids & real_tag_ids
    ]
