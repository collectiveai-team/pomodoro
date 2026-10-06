"""Per-User Tag catalog rules.

Pure core: no FastAPI/SQLModel/Pydantic imports. Every rule here is scoped to
a single User; callers are responsible for passing in only that User's Tags.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from pomodoro.core.errors import DuplicateTagNameError, TagNameEmptyError
from pomodoro.core.normalization import normalize_key

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pomodoro.core.entities import Tag, TagId, Task


def validate_tag_name(name: str) -> str:
    """Return the trimmed name, or raise if it is empty after stripping."""
    stripped = name.strip()
    if not stripped:
        raise TagNameEmptyError
    return stripped


def _name_collides(
    name: str,
    tags: Sequence[Tag],
    *,
    exclude_tag_id: TagId | None = None,
) -> bool:
    key = normalize_key(name)
    return any(tag.id != exclude_tag_id and tag.name_key == key for tag in tags)


def ensure_unique_tag_name(
    name: str,
    tags: Sequence[Tag],
    *,
    exclude_tag_id: TagId | None = None,
) -> None:
    """Raise if `name` normalizes to the same key as one of `tags`."""
    if _name_collides(name, tags, exclude_tag_id=exclude_tag_id):
        raise DuplicateTagNameError


def find_tag_by_name(name: str, tags: Sequence[Tag]) -> Tag | None:
    """Return the Tag among `tags` whose normalized key matches `name`, if any."""
    key = normalize_key(name)
    return next((tag for tag in tags if tag.name_key == key), None)


def rename_tag(tag: Tag, new_name: str, tags: Sequence[Tag]) -> Tag:
    """Validate and apply a rename; reject a collision with another of the User's Tags.

    Renaming only changes this Tag row; every Task that carries it (by `TagId`)
    reflects the new name without any Task being touched.
    """
    stripped = validate_tag_name(new_name)
    ensure_unique_tag_name(stripped, tags, exclude_tag_id=tag.id)
    return replace(tag, name=stripped, name_key=normalize_key(stripped))


def detach_tag(tag_id: TagId, tasks: Sequence[Task]) -> list[Task]:
    """Return `tasks` with `tag_id` removed from every Task that carried it."""
    return [
        replace(task, tag_ids=tuple(tid for tid in task.tag_ids if tid != tag_id))
        if tag_id in task.tag_ids
        else task
        for task in tasks
    ]
