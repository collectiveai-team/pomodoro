"""Unit tests for Tag catalog rules and the TagRepository Protocol."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from pomodoro.core.entities import Tag, TagId, Task, TaskId, UserId
from pomodoro.core.errors import DuplicateTagNameError, TagNameEmptyError
from pomodoro.core.normalization import normalize_key
from pomodoro.core.repositories import TagRepository
from pomodoro.core.tags import (
    detach_tag,
    ensure_unique_tag_name,
    find_tag_by_name,
    rename_tag,
    validate_tag_name,
)

USER = UserId(1)
OTHER_USER = UserId(2)


def make_tag(*, id: int = 1, user_id: UserId = USER, name: str = "Trabajo") -> Tag:
    return Tag(id=TagId(id), user_id=user_id, name=name, name_key=normalize_key(name))


# --- validate_tag_name -------------------------------------------------------


def test_validate_tag_name_strips_whitespace() -> None:
    assert validate_tag_name("  Urgente  ") == "Urgente"


def test_validate_tag_name_rejects_empty_after_stripping() -> None:
    with pytest.raises(TagNameEmptyError):
        validate_tag_name("   ")


# --- normalization / lookup ---------------------------------------------------


def test_find_tag_by_name_matches_case_and_whitespace_insensitively() -> None:
    tag = make_tag(name="Trabajo")
    assert find_tag_by_name(" trabajo ", [tag]) is tag
    assert find_tag_by_name("TRABAJO", [tag]) is tag


def test_find_tag_by_name_returns_none_when_absent() -> None:
    assert find_tag_by_name("Urgente", [make_tag(name="Trabajo")]) is None


def test_ensure_unique_tag_name_rejects_normalized_collision() -> None:
    with pytest.raises(DuplicateTagNameError):
        ensure_unique_tag_name("  trabajo ", [make_tag(id=1, name="Trabajo")])


def test_ensure_unique_tag_name_allows_excluding_self() -> None:
    tag = make_tag(id=1, name="Trabajo")
    ensure_unique_tag_name("Trabajo", [tag], exclude_tag_id=tag.id)


# --- rename_tag ----------------------------------------------------------------


def test_rename_tag_updates_name_and_key() -> None:
    tag = make_tag(id=1, name="Trabajo")
    renamed = rename_tag(tag, "Urgente", [tag])
    assert renamed.name == "Urgente"
    assert renamed.name_key == normalize_key("Urgente")
    assert renamed.id == tag.id


def test_rename_tag_rejects_empty_name() -> None:
    tag = make_tag(id=1, name="Trabajo")
    with pytest.raises(TagNameEmptyError):
        rename_tag(tag, "   ", [tag])


def test_rename_tag_rejects_collision_with_another_tag() -> None:
    tag = make_tag(id=1, name="Trabajo")
    other = make_tag(id=2, name="Urgente")
    with pytest.raises(DuplicateTagNameError):
        rename_tag(tag, " urgente ", [tag, other])


def test_rename_tag_allows_keeping_its_own_unchanged_name() -> None:
    tag = make_tag(id=1, name="Trabajo")
    renamed = rename_tag(tag, "Trabajo", [tag])
    assert renamed.name == "Trabajo"


def test_rename_tag_propagates_to_every_task_carrying_it_since_its_the_same_row() -> None:
    """Tasks reference a Tag by id; renaming the row is all that's needed."""
    tag = make_tag(id=1, name="Trabajo")
    task_a = Task(
        id=TaskId(1),
        user_id=USER,
        text="A",
        position=0,
        tag_ids=(tag.id,),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        archived_at=None,
    )
    renamed = rename_tag(tag, "Urgente", [tag])
    catalog = {renamed.id: renamed}
    assert catalog[task_a.tag_ids[0]].name == "Urgente"


# --- detach_tag (delete cascade) ------------------------------------------------


def test_detach_tag_removes_the_tag_id_from_every_task_that_had_it() -> None:
    tag_id = TagId(1)
    other_tag_id = TagId(2)
    task_with = replace(_blank_task(1), tag_ids=(tag_id, other_tag_id))
    task_without = replace(_blank_task(2), tag_ids=(other_tag_id,))
    result = detach_tag(tag_id, [task_with, task_without])
    by_id = {t.id: t for t in result}
    assert by_id[task_with.id].tag_ids == (other_tag_id,)
    assert by_id[task_without.id].tag_ids == (other_tag_id,)


def test_detach_tag_leaves_unaffected_tasks_untouched() -> None:
    task = _blank_task(1, tag_ids=(TagId(9),))
    result = detach_tag(TagId(1), [task])
    assert result == [task]


def _blank_task(id: int, *, tag_ids: tuple[TagId, ...] = ()) -> Task:
    return Task(
        id=TaskId(id),
        user_id=USER,
        text=f"Task {id}",
        position=0,
        tag_ids=tag_ids,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        archived_at=None,
    )


# --- TagRepository Protocol, orphan retention, per-User scoping -----------------


class FakeTagRepository:
    """In-memory TagRepository used to confirm the Protocol's shape and rules."""

    def __init__(self) -> None:
        self._tags: dict[TagId, Tag] = {}
        self._next_id = 1

    def list(self, user_id: UserId) -> list[Tag]:
        return [t for t in self._tags.values() if t.user_id == user_id]

    def get_or_create_by_name(self, user_id: UserId, name: str) -> Tag:
        stripped = validate_tag_name(name)
        existing = find_tag_by_name(stripped, self.list(user_id))
        if existing is not None:
            return existing
        tag = Tag(
            id=TagId(self._next_id),
            user_id=user_id,
            name=stripped,
            name_key=normalize_key(stripped),
        )
        self._next_id += 1
        self._tags[tag.id] = tag
        return tag

    def rename(self, user_id: UserId, tag_id: TagId, new_name: str) -> Tag:
        tag = self._tags[tag_id]
        renamed = rename_tag(tag, new_name, self.list(user_id))
        self._tags[tag_id] = renamed
        return renamed

    def delete(self, user_id: UserId, tag_id: TagId) -> None:
        tag = self._tags.get(tag_id)
        if tag is not None and tag.user_id == user_id:
            del self._tags[tag_id]


def test_fake_tag_repository_satisfies_the_protocol() -> None:
    repo: TagRepository = FakeTagRepository()
    assert isinstance(repo, TagRepository)


def test_get_or_create_by_name_creates_then_reuses_by_normalized_key() -> None:
    repo = FakeTagRepository()
    first = repo.get_or_create_by_name(USER, "Trabajo")
    second = repo.get_or_create_by_name(USER, "  trabajo ")
    assert first.id == second.id
    assert repo.list(USER) == [first]


def test_get_or_create_by_name_is_scoped_per_user() -> None:
    repo = FakeTagRepository()
    mine = repo.get_or_create_by_name(USER, "Trabajo")
    theirs = repo.get_or_create_by_name(OTHER_USER, "Trabajo")
    assert mine.id != theirs.id
    assert mine.user_id != theirs.user_id
    assert repo.list(USER) == [mine]
    assert repo.list(OTHER_USER) == [theirs]


def test_rename_via_repository_rejects_duplicate() -> None:
    repo = FakeTagRepository()
    repo.get_or_create_by_name(USER, "Trabajo")
    urgente = repo.get_or_create_by_name(USER, "Urgente")
    with pytest.raises(DuplicateTagNameError):
        repo.rename(USER, urgente.id, "trabajo")


def test_delete_removes_from_catalog_and_an_orphan_without_delete_stays() -> None:
    repo = FakeTagRepository()
    kept = repo.get_or_create_by_name(USER, "Sin uso")
    to_delete = repo.get_or_create_by_name(USER, "Temporal")
    repo.delete(USER, to_delete.id)
    assert repo.list(USER) == [kept]
