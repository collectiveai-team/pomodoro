"""CES-17 · Tag catalog endpoints: list, update, delete (T8).

Same FastAPI type-hint-resolution caveat as `tasks/routers.py`: every annotated name must be a
real, module-level import, never `TYPE_CHECKING`-only.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from pomodoro.api.v1.auth.dependencies import get_current_user
from pomodoro.api.v1.schemas.responses.error import ErrorResponse
from pomodoro.api.v1.tags.schemas.requests.update_tag import UpdateTagRequest
from pomodoro.api.v1.tags.schemas.responses.tag import TagResponse
from pomodoro.api.v1.tags.schemas.responses.tag_list import TagListResponse
from pomodoro.api.v1.tags.use_cases import delete_tag, list_tags, update_tag
from pomodoro.core.tags import Tag, TagId, TagRepository
from pomodoro.core.users import User
from pomodoro.database.repositories.tag import get_tag_repository

router = APIRouter(prefix="/tags", tags=["tags"])

_AUTH_ERROR_RESPONSE: dict[int | str, dict[str, Any]] = {401: {"model": ErrorResponse}}
_TAG_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_AUTH_ERROR_RESPONSE,
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


def _tag_response(tag: Tag) -> TagResponse:
    return TagResponse(id=tag.id, name=tag.name, color=tag.color)


@router.get("", responses=_AUTH_ERROR_RESPONSE)
def list_all(
    user: User = Depends(get_current_user),
    tag_repository: TagRepository = Depends(get_tag_repository),
) -> TagListResponse:
    """List the caller's full Tag catalog."""
    tags = list_tags(user_id=user.id, tag_repository=tag_repository)
    return TagListResponse(tags=[_tag_response(tag) for tag in tags])


@router.patch("/{tag_id}", responses=_TAG_ERROR_RESPONSES)
def update(
    tag_id: UUID,
    payload: UpdateTagRequest,
    user: User = Depends(get_current_user),
    tag_repository: TagRepository = Depends(get_tag_repository),
) -> TagResponse:
    """Update a Tag's name and/or color; changes are visible on every Task that carries it."""
    tag = update_tag(
        user_id=user.id,
        tag_id=TagId(tag_id),
        name=payload.name,
        color=payload.color,
        tag_repository=tag_repository,
    )
    return _tag_response(tag)


@router.delete("/{tag_id}", status_code=204, responses=_TAG_ERROR_RESPONSES)
def delete(
    tag_id: UUID,
    user: User = Depends(get_current_user),
    tag_repository: TagRepository = Depends(get_tag_repository),
) -> None:
    """Permanently remove a Tag from the catalog and from every Task that carries it."""
    delete_tag(user_id=user.id, tag_id=TagId(tag_id), tag_repository=tag_repository)
