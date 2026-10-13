"""Tag catalog use cases: the orchestration `routers.py` delegates to (T8).

`resolve_tag_ids_by_names` also backs `api.v1.tasks`' "set a Task's Tags by name" endpoint, since
create-or-reuse-by-name is a Tag-domain operation regardless of which router triggers it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import uuid4

from pomodoro.core.logger import get_logger
from pomodoro.core.tags import (
    Tag,
    TagId,
    TagNotFoundError,
    TagRepository,
    ensure_unique_tag_name,
    find_tag_by_name_key,
    normalize_tag_name,
    validate_tag_name,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pomodoro.core.users import UserId

log = get_logger(__name__)


def resolve_tag_ids_by_names(
    *, user_id: UserId, names: Sequence[str], tag_repository: TagRepository
) -> list[TagId]:
    """Resolve `names` to their Tag ids, creating a new Tag when no match exists by `name_key`.

    Duplicate names (once normalized), including duplicates within `names` itself, resolve to
    the same Tag id without creating duplicate rows, and appear only once in the result.
    """
    existing_tags = tag_repository.list_all(user_id)
    resolved_by_key: dict[str, TagId] = {}
    for raw_name in names:
        name = validate_tag_name(raw_name)
        name_key = normalize_tag_name(name)
        if name_key in resolved_by_key:
            continue
        existing_tag = find_tag_by_name_key(name_key, existing_tags)
        if existing_tag is None:
            existing_tag = Tag(id=TagId(uuid4()), user_id=user_id, name=name, name_key=name_key)
            tag_repository.add(existing_tag)
            existing_tags.append(existing_tag)
        resolved_by_key[name_key] = existing_tag.id
    return list(resolved_by_key.values())


def list_tags(*, user_id: UserId, tag_repository: TagRepository) -> list[Tag]:
    """Return the caller's full Tag catalog."""
    return tag_repository.list_all(user_id)


def rename_tag(*, user_id: UserId, tag_id: TagId, name: str, tag_repository: TagRepository) -> Tag:
    """Rename a Tag, rejecting a collision with another of the caller's Tags.

    Raises `TagNotFoundError` when the Tag does not exist or belongs to another User.
    """
    tag = tag_repository.get_by_id(user_id, tag_id)
    if tag is None:
        raise TagNotFoundError(f"Tag {tag_id} not found.")

    validated_name = validate_tag_name(name)
    name_key = normalize_tag_name(validated_name)
    existing_tags = tag_repository.list_all(user_id)
    ensure_unique_tag_name(name_key=name_key, existing_tags=existing_tags, exclude_tag_id=tag_id)

    tag_repository.update_name(user_id, tag_id, validated_name, name_key)

    log.info("tag_renamed", tag_id=str(tag_id))
    return replace(tag, name=validated_name, name_key=name_key)


def delete_tag(*, user_id: UserId, tag_id: TagId, tag_repository: TagRepository) -> None:
    """Permanently remove a Tag, cascading to every Task that carries it.

    Raises `TagNotFoundError` when the Tag does not exist or belongs to another User.
    """
    tag = tag_repository.get_by_id(user_id, tag_id)
    if tag is None:
        raise TagNotFoundError(f"Tag {tag_id} not found.")

    tag_repository.delete(user_id, tag_id)

    log.info("tag_deleted", tag_id=str(tag_id))
