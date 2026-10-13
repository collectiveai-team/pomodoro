"""The `Tag` entity, its domain errors, and the repository Protocol it needs (ADR-0002).

A Tag is scoped per User: assigning one by name creates it or reuses an existing one matched by
its normalized `name_key`, so two Users may share a Tag name without sharing the row. A Task only
ever stores a Tag's id (`Task.tag_ids`, see `core.tasks`), never a copy of its name — renaming a
Tag therefore propagates everywhere it's carried for free, since every carrier points at the same
row. Deleting a Tag relies on the `task_tags` join table's `ON DELETE CASCADE` to detach it from
every Task without application-level fan-out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NewType, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pomodoro.core.users import UserId

TagId = NewType("TagId", UUID)


class EmptyTagNameError(ValueError):
    """Raised when a Tag's name is empty once leading/trailing whitespace is stripped."""


class DuplicateTagNameError(ValueError):
    """Raised when a Tag's name matches another of the same User's Tags, once normalized."""


class TagNotFoundError(LookupError):
    """Raised when a Tag does not exist, or does not belong to the caller."""


@dataclass(frozen=True, slots=True)
class Tag:
    """A User-scoped label a Task can carry zero or more of."""

    id: TagId
    user_id: UserId
    name: str
    name_key: str


def normalize_tag_name(name: str) -> str:
    """Return the comparison key for a Tag's name: `strip().casefold()`."""
    return name.strip().casefold()


def validate_tag_name(name: str) -> str:
    """Return `name` stripped, raising `EmptyTagNameError` if it is empty."""
    stripped = name.strip()
    if not stripped:
        raise EmptyTagNameError("Tag name cannot be empty.")
    return stripped


def find_tag_by_name_key(name_key: str, tags: Iterable[Tag]) -> Tag | None:
    """Return the first Tag in `tags` whose `name_key` matches, or None."""
    return next((tag for tag in tags if tag.name_key == name_key), None)


def ensure_unique_tag_name(
    *, name_key: str, existing_tags: Iterable[Tag], exclude_tag_id: TagId | None = None
) -> None:
    """Raise `DuplicateTagNameError` if another of the User's Tags already has this `name_key`."""
    for tag in existing_tags:
        if tag.id == exclude_tag_id:
            continue
        if tag.name_key == name_key:
            raise DuplicateTagNameError(f"A Tag with this name already exists: '{tag.name}'.")


class TagRepository(Protocol):
    """Persistence Protocol for `Tag`, scoped to a `UserId` (implemented by `database`)."""

    def add(self, tag: Tag) -> None:
        """Persist a newly created Tag."""
        ...

    def get_by_id(self, user_id: UserId, tag_id: TagId) -> Tag | None:
        """Return the caller's Tag with this id, or None if absent or owned by another User."""
        ...

    def list_all(self, user_id: UserId) -> list[Tag]:
        """Return every Tag in the caller's catalog, including ones carried by no Task."""
        ...

    def update_name(self, user_id: UserId, tag_id: TagId, name: str, name_key: str) -> None:
        """Overwrite a Tag's name and derived key."""
        ...

    def delete(self, user_id: UserId, tag_id: TagId) -> None:
        """Permanently remove the caller's Tag, cascading to every Task that carries it."""
        ...
