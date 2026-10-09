"""Per-User Tag rules (core, T5): assign-by-name, rename, cascade delete.

Pure functions over `Tag`/`Task` snapshots scoped to a single `User` — like
`core.tasks`, callers pass in the relevant `Tag`s/`Task`s already scoped to the
User and get back the updated snapshot(s). Deleting a Tag never asks for
confirmation (issue #12 spec) and never removes the now-possibly-orphaned Tag
from the catalog: that stays available for reuse.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from pomodoro.core.entities import Tag
from pomodoro.core.errors import TagNameEmptyError, TagRenameCollisionError
from pomodoro.core.normalization import tag_name_key

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pomodoro.core.entities import TagId, Task, UserId


def _validate_name(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        raise TagNameEmptyError
    return stripped


def resolve_tag(tags: Sequence[Tag], *, new_tag_id: TagId, user_id: UserId, name: str) -> Tag:
    """Create-or-reuse a Tag by its normalized `name_key` (assign-by-name)."""
    validated_name = _validate_name(name)
    key = tag_name_key(validated_name)
    existing = next((tag for tag in tags if tag.name_key == key), None)
    if existing is not None:
        return existing
    return Tag(id=new_tag_id, user_id=user_id, name=validated_name)


def rename_tag(tags: Sequence[Tag], tag: Tag, *, name: str) -> Tag:
    """Rename a Tag in place (same id), rejecting a collision with another Tag."""
    validated_name = _validate_name(name)
    key = tag_name_key(validated_name)
    collision = next(
        (other for other in tags if other.id != tag.id and other.name_key == key), None
    )
    if collision is not None:
        raise TagRenameCollisionError(validated_name)
    return replace(tag, name=validated_name)


def delete_tag(tasks: Sequence[Task], tag_id: TagId) -> list[Task]:
    """Cascade-remove `tag_id` from every Task that carries it, no confirmation.

    Only touches `Task.tag_ids`; the Tag catalog entry itself is left for the
    caller to remove, so a Tag left with zero Tasks is simply orphaned, not
    deleted.
    """
    return [
        replace(task, tag_ids=task.tag_ids - {tag_id}) if tag_id in task.tag_ids else task
        for task in tasks
    ]
