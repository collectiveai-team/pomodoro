"""Tests for the per-User Tag rules in core/ (T5)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pomodoro.core.entities import Tag, TagId, Task, TaskId, UserId
from pomodoro.core.errors import TagNameEmptyError, TagRenameCollisionError
from pomodoro.core.tags import delete_tag, rename_tag, resolve_tag

pytestmark = pytest.mark.unit

_USER = UserId(1)


def _tag(*, id: int = 1, name: str = "Trabajo") -> Tag:
    return Tag(id=TagId(id), user_id=_USER, name=name)


class TestResolveTag:
    def test_creates_a_new_tag_when_no_existing_one_matches(self) -> None:
        tag = resolve_tag([], new_tag_id=TagId(1), user_id=_USER, name="Trabajo")
        assert tag == Tag(id=TagId(1), user_id=_USER, name="Trabajo")

    @pytest.mark.parametrize("name", ["Trabajo", "trabajo", " trabajo ", "TRABAJO"])
    def test_reuses_an_existing_tag_by_normalized_key(self, name: str) -> None:
        existing = _tag(id=7, name="Trabajo")
        resolved = resolve_tag([existing], new_tag_id=TagId(99), user_id=_USER, name=name)
        assert resolved == existing

    def test_rejects_an_empty_name(self) -> None:
        with pytest.raises(TagNameEmptyError):
            resolve_tag([], new_tag_id=TagId(1), user_id=_USER, name="   ")

    def test_strips_surrounding_whitespace_on_create(self) -> None:
        tag = resolve_tag([], new_tag_id=TagId(1), user_id=_USER, name="  Trabajo  ")
        assert tag.name == "Trabajo"


class TestRenameTag:
    def test_renames_in_place_keeping_the_same_id(self) -> None:
        tag = _tag(id=1, name="Trabajo")
        renamed = rename_tag([tag], tag, name="Oficina")
        assert renamed.id == tag.id
        assert renamed.name == "Oficina"

    def test_renaming_to_its_own_current_name_is_not_a_collision(self) -> None:
        tag = _tag(id=1, name="Trabajo")
        renamed = rename_tag([tag], tag, name="Trabajo")
        assert renamed.name == "Trabajo"

    @pytest.mark.parametrize("new_name", ["Oficina", "oficina", " oficina ", "OFICINA"])
    def test_rejects_rename_colliding_with_another_tag_by_normalized_key(
        self, new_name: str
    ) -> None:
        tag = _tag(id=1, name="Trabajo")
        other = _tag(id=2, name="Oficina")
        with pytest.raises(TagRenameCollisionError):
            rename_tag([tag, other], tag, name=new_name)

    def test_rejects_an_empty_name(self) -> None:
        tag = _tag(id=1, name="Trabajo")
        with pytest.raises(TagNameEmptyError):
            rename_tag([tag], tag, name="  ")


class TestDeleteTag:
    def _task(self, *, id: int = 1, tag_ids: frozenset[TagId] = frozenset()) -> Task:
        return Task(
            id=TaskId(id),
            user_id=_USER,
            text="x",
            position=0,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            tag_ids=tag_ids,
        )

    def test_cascades_removal_from_every_task_that_carries_it(self) -> None:
        tag_id = TagId(1)
        other_id = TagId(2)
        task_with_tag = self._task(id=1, tag_ids=frozenset({tag_id, other_id}))
        task_without_tag = self._task(id=2, tag_ids=frozenset({other_id}))

        updated = delete_tag([task_with_tag, task_without_tag], tag_id)

        updated_by_id = {task.id: task for task in updated}
        assert updated_by_id[task_with_tag.id].tag_ids == frozenset({other_id})
        assert updated_by_id[task_without_tag.id].tag_ids == frozenset({other_id})

    def test_leaves_a_task_without_the_tag_untouched(self) -> None:
        task = self._task(id=1, tag_ids=frozenset({TagId(2)}))
        (updated,) = delete_tag([task], TagId(1))
        assert updated == task

    def test_orphaned_tag_is_retained_in_the_catalog(self) -> None:
        """Deleting a Tag's Task associations never touches the Tag catalog itself."""
        tag = _tag(id=1)
        catalog = [tag]
        task = self._task(id=1, tag_ids=frozenset({tag.id}))

        delete_tag([task], tag.id)

        assert catalog == [tag]
