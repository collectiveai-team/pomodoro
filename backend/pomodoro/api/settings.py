"""Settings API: read and update the current User's alarm/notifications/time_zone.

Per the house convention (api/<area> owns router + schemas + use case), the
orchestration lives here; `pomodoro.core.auth` supplies the framework-free
`time_zone` validation and `pomodoro.api.session` supplies the authenticated
`User` every route below requires. Changing `time_zone` never recomputes or
stores anything else: History is a derived view over `ended_at` in UTC.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from pomodoro.api.session import get_user_repository, require_session
from pomodoro.core.auth import validate_time_zone
from pomodoro.core.entities import User
from pomodoro.core.errors import InvalidTimeZoneError
from pomodoro.core.repositories import UserRepository

router = APIRouter(prefix="/api/settings", tags=["settings"])

UserDep = Annotated[User, Depends(require_session)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]


class SettingsPublic(BaseModel):
    """The User's preference fields exposed over HTTP."""

    alarm_enabled: bool
    notifications_enabled: bool
    time_zone: str

    @classmethod
    def from_entity(cls, user: User) -> SettingsPublic:
        return cls(
            alarm_enabled=user.alarm_enabled,
            notifications_enabled=user.notifications_enabled,
            time_zone=user.time_zone,
        )


class UpdateSettingsRequest(BaseModel):
    """Request body for `PATCH /api/settings`; every field is optional."""

    alarm_enabled: bool | None = None
    notifications_enabled: bool | None = None
    time_zone: str | None = None


@router.get("")
def get_settings_route(user: UserDep) -> SettingsPublic:
    """Return the current User's alarm/notifications/time_zone preferences."""
    return SettingsPublic.from_entity(user)


@router.patch("")
def update_settings_route(
    body: UpdateSettingsRequest, user: UserDep, user_repo: UserRepoDep
) -> SettingsPublic:
    """Update any subset of the User's preferences and persist the result."""
    if body.time_zone is not None:
        try:
            validate_time_zone(body.time_zone)
        except InvalidTimeZoneError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error

    updated = user
    if body.alarm_enabled is not None:
        updated = replace(updated, alarm_enabled=body.alarm_enabled)
    if body.notifications_enabled is not None:
        updated = replace(updated, notifications_enabled=body.notifications_enabled)
    if body.time_zone is not None:
        updated = replace(updated, time_zone=body.time_zone)
    stored = user_repo.update(updated)
    return SettingsPublic.from_entity(stored)
