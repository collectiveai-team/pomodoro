"""Tags API: list the User's Tag catalog, rename a Tag, delete a Tag.

Per the house convention (api/<area> owns router + schemas + use case), the
orchestration lives here; `pomodoro.core.tags` supplies the framework-free
rename validation and `pomodoro.api.session` supplies the authenticated
`User` every route below requires. `TagRepository` is reused from
`pomodoro.api.tasks` rather than wired a second time.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from pomodoro.api.session import require_session
from pomodoro.api.tasks import get_tag_repository
from pomodoro.core.entities import Tag, TagId, User
from pomodoro.core.errors import DuplicateTagNameError, TagNameEmptyError
from pomodoro.core.repositories import TagRepository
from pomodoro.core.tags import rename_tag

router = APIRouter(prefix="/api/tags", tags=["tags"])


UserDep = Annotated[User, Depends(require_session)]
TagRepoDep = Annotated[TagRepository, Depends(get_tag_repository)]

NOT_FOUND_ERROR = "La etiqueta no existe."


class RenameTagRequest(BaseModel):
    """Request body for `PATCH /api/tags/{tag_id}`."""

    name: str


class TagPublic(BaseModel):
    """A Tag as exposed over HTTP."""

    id: int
    name: str

    @classmethod
    def from_entity(cls, tag: Tag) -> TagPublic:
        return cls(id=tag.id, name=tag.name)


def _get_owned_tag(catalog: list[Tag], tag_id: int) -> Tag:
    tag = next((candidate for candidate in catalog if candidate.id == tag_id), None)
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_ERROR)
    return tag


@router.get("")
def list_tags(user: UserDep, tag_repo: TagRepoDep) -> list[TagPublic]:
    """Return the User's full Tag catalog, including orphaned Tags."""
    return [TagPublic.from_entity(tag) for tag in tag_repo.list(user.id)]


@router.patch("/{tag_id}")
def rename_tag_route(
    tag_id: int, body: RenameTagRequest, user: UserDep, tag_repo: TagRepoDep
) -> TagPublic:
    """Rename a Tag; every Task carrying it reflects the new name without being touched."""
    catalog = tag_repo.list(user.id)
    tag = _get_owned_tag(catalog, tag_id)
    try:
        renamed = rename_tag(tag, body.name, catalog)
    except DuplicateTagNameError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except TagNameEmptyError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    stored = tag_repo.rename(user.id, TagId(tag_id), renamed.name)
    return TagPublic.from_entity(stored)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag_route(tag_id: int, user: UserDep, tag_repo: TagRepoDep) -> None:
    """Delete a Tag; it's removed from every Task that had it, no confirmation required."""
    catalog = tag_repo.list(user.id)
    _get_owned_tag(catalog, tag_id)
    tag_repo.delete(user.id, TagId(tag_id))
