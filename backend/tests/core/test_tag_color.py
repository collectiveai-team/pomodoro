"""Tag color palette and auto-assignment, driven through the Tag use cases."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pomodoro.api.v1.tags.use_cases import rename_tag, resolve_tag_ids_by_names
from pomodoro.core.tags import Tag, TagColor, TagId, normalize_tag_name, pick_tag_color
from pomodoro.core.users import UserId

pytestmark = pytest.mark.unit

USER_ID = UserId(UUID(int=1))
PALETTE = list(TagColor)


class InMemoryTagRepository:
    def __init__(self) -> None:
        self.tags: dict[TagId, Tag] = {}

    def add(self, tag: Tag) -> None:
        self.tags[tag.id] = tag

    def get_by_id(self, user_id: UserId, tag_id: TagId) -> Tag | None:
        tag = self.tags.get(tag_id)
        return tag if tag is not None and tag.user_id == user_id else None

    def list_all(self, user_id: UserId) -> list[Tag]:
        return [tag for tag in self.tags.values() if tag.user_id == user_id]

    def update_name(self, user_id: UserId, tag_id: TagId, name: str, name_key: str) -> None:
        tag = self.tags[tag_id]
        self.tags[tag_id] = Tag(tag_id, user_id, name, name_key, tag.color)

    def delete(self, user_id: UserId, tag_id: TagId) -> None:
        self.tags.pop(tag_id, None)


def _tag(name: str, color: TagColor) -> Tag:
    return Tag(TagId(uuid4()), USER_ID, name, normalize_tag_name(name), color)


def test_palette_has_eight_stable_keys_in_fixed_order() -> None:
    assert [c.value for c in PALETTE] == [
        "rose", "orange", "amber", "green", "teal", "sky", "violet", "slate",
    ]  # fmt: skip


def test_no_tags_picks_first_color() -> None:
    assert pick_tag_color([]) == TagColor.ROSE


def test_picks_least_used_color() -> None:
    tags = [_tag(f"t{i}", c) for i, c in enumerate(PALETTE) if c != TagColor.TEAL]
    tags.append(_tag("extra", TagColor.ROSE))
    assert pick_tag_color(tags) == TagColor.TEAL


def test_tie_broken_by_palette_order() -> None:
    tags = [_tag("a", TagColor.ROSE), _tag("b", TagColor.ORANGE)]
    assert pick_tag_color(tags) == TagColor.AMBER


def test_created_by_name_tags_get_successive_palette_colors() -> None:
    repo = InMemoryTagRepository()
    ids = resolve_tag_ids_by_names(
        user_id=USER_ID, names=["uno", "dos", "tres"], tag_repository=repo
    )
    assert [repo.tags[i].color for i in ids] == PALETTE[:3]


def test_rename_keeps_color() -> None:
    repo = InMemoryTagRepository()
    (tag_id,) = resolve_tag_ids_by_names(user_id=USER_ID, names=["uno"], tag_repository=repo)
    repo.tags[tag_id] = Tag(tag_id, USER_ID, "uno", "uno", TagColor.SKY)

    renamed = rename_tag(user_id=USER_ID, tag_id=tag_id, name="nuevo", tag_repository=repo)

    assert renamed.color == TagColor.SKY
    assert repo.tags[tag_id].color == TagColor.SKY
