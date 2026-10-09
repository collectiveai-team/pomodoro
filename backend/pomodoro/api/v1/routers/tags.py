"""Tags API: list the catalog, rename, delete (cascading off every Task, T12).

Thin handlers: the rename-collision rule lives in the T12
`SqlTagRepository.update_name` (a `name_key` unique-constraint violation, same
shape as `SqlTaskRepository.update_text`'s duplicate-text rule), and delete
cascades via the `task_tags` table's `ON DELETE CASCADE` FKs (T2) rather than
an application-level cleanup step. Every repository call is scoped to the
authenticated User's `UserId` (CES-18), so cross-User leakage is impossible by
construction. Creating a Tag (assign-by-name) is out of this ticket's scope -
`core.tags.resolve_tag` is wired up by whichever future ticket adds Tag
assignment to a Task.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from pomodoro.api.v1 import dependencies as deps
from pomodoro.api.v1.schemas.requests.tags import RenameTagRequest
from pomodoro.api.v1.schemas.responses.tags import TagResponse
from pomodoro.api.v1.session import require_json_content_type
from pomodoro.core.entities import TagId
from pomodoro.core.tags import rename_tag
from pomodoro.database.tag_repository import SqlTagRepository

if TYPE_CHECKING:
    from pomodoro.core.entities import AuthSession, Tag

router = APIRouter(prefix="/tags", tags=["tags"], dependencies=[Depends(require_json_content_type)])


def _to_response(tag: Tag) -> TagResponse:
    return TagResponse(id=tag.id, name=tag.name)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found.")


@router.get("")
def list_tags(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> list[TagResponse]:
    """List the authenticated User's Tag catalog, including Tags with zero Tasks."""
    repo = SqlTagRepository(db_session)
    return [_to_response(tag) for tag in repo.list_for_user(auth_session.user_id)]


@router.put("/{tag_id}")
def rename(
    tag_id: int,
    payload: RenameTagRequest,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> TagResponse:
    """Rename a Tag, rejecting a collision with another of the User's Tags."""
    repo = SqlTagRepository(db_session)
    tag = repo.get(auth_session.user_id, TagId(tag_id))
    if tag is None:
        raise _not_found()
    tags = repo.list_for_user(auth_session.user_id)
    validated = rename_tag(tags, tag, name=payload.name)
    updated = repo.update_name(auth_session.user_id, TagId(tag_id), name=validated.name)
    return _to_response(updated)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    tag_id: int,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> None:
    """Delete a Tag, cascading off every Task that carries it - no confirmation needed."""
    repo = SqlTagRepository(db_session)
    if repo.get(auth_session.user_id, TagId(tag_id)) is None:
        raise _not_found()
    repo.delete(auth_session.user_id, TagId(tag_id))
