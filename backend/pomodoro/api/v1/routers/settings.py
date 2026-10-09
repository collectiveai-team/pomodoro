"""Settings API: read & update alarm/notifications/time_zone (T15).

Thin handlers: `core.time_zone.validate_time_zone` is the one time-zone
validity rule, reused unchanged from T9's register rather than duplicated
here. Each preference is independently updatable - a client sends only the
field(s) it wants to change - via `dataclasses.replace` over the User read
fresh from `SqlUserRepository.get_by_id`, then persisted through the existing
T7 `UserRepository.update`. Every lookup is scoped to the authenticated
User's `UserId` (`auth_session.user_id`), mirroring T10-T14's
per-User-isolation-by-construction template. Because every later read (the
T13 day summary today, History in T16/T17) re-fetches the User's `time_zone`
from this same row rather than caching it anywhere, an update here takes
effect immediately for any such read, with no extra plumbing needed.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from pomodoro.api.v1 import dependencies as deps
from pomodoro.api.v1.schemas.requests.settings import UpdateSettingsRequest
from pomodoro.api.v1.schemas.responses.settings import SettingsResponse
from pomodoro.api.v1.session import require_json_content_type
from pomodoro.core.time_zone import validate_time_zone
from pomodoro.database.user_repository import SqlUserRepository

if TYPE_CHECKING:
    from pomodoro.core.entities import AuthSession, User

router = APIRouter(
    prefix="/settings", tags=["settings"], dependencies=[Depends(require_json_content_type)]
)


def _to_response(user: User) -> SettingsResponse:
    return SettingsResponse(
        time_zone=user.time_zone,
        alarm_enabled=user.alarm_enabled,
        notifications_enabled=user.notifications_enabled,
    )


def _require_user(db_session: Session, auth_session: AuthSession) -> User:
    user = SqlUserRepository(db_session).get_by_id(auth_session.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return user


@router.get("")
def read_settings(
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> SettingsResponse:
    """Return the authenticated User's Alarm/notifications/time_zone preferences."""
    return _to_response(_require_user(db_session, auth_session))


@router.patch("")
def update_settings(
    payload: UpdateSettingsRequest,
    auth_session: AuthSession = Depends(deps.require_session),
    db_session: Session = Depends(deps.get_db_session),
) -> SettingsResponse:
    """Update one or more preferences in place, validating `time_zone` when provided."""
    user = _require_user(db_session, auth_session)
    if payload.time_zone is not None:
        validate_time_zone(payload.time_zone)

    updated = replace(
        user,
        time_zone=payload.time_zone if payload.time_zone is not None else user.time_zone,
        alarm_enabled=(
            payload.alarm_enabled if payload.alarm_enabled is not None else user.alarm_enabled
        ),
        notifications_enabled=(
            payload.notifications_enabled
            if payload.notifications_enabled is not None
            else user.notifications_enabled
        ),
    )
    return _to_response(SqlUserRepository(db_session).update(updated))
