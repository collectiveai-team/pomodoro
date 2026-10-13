"""CES-17 · Settings endpoints: read and update Alarm, notifications, time zone (T15).

Same FastAPI type-hint-resolution caveat as `tags/routers.py`: every annotated name must be a
real, module-level import, never `TYPE_CHECKING`-only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pomodoro.api.v1.auth.dependencies import get_current_user
from pomodoro.api.v1.settings.schemas.requests.update_settings import UpdateSettingsRequest
from pomodoro.api.v1.settings.schemas.responses.settings import SettingsResponse
from pomodoro.api.v1.settings.use_cases import update_settings
from pomodoro.core.users import User, UserRepository
from pomodoro.database.repositories.user import get_user_repository

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_response(user: User) -> SettingsResponse:
    return SettingsResponse(
        alarm_enabled=user.alarm_enabled,
        notifications_enabled=user.notifications_enabled,
        time_zone=user.time_zone,
    )


@router.get("")
def read(user: User = Depends(get_current_user)) -> SettingsResponse:
    """Return the caller's current Alarm, notification, and time-zone preferences."""
    return _settings_response(user)


@router.patch("")
def update(
    payload: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    user_repository: UserRepository = Depends(get_user_repository),
) -> SettingsResponse:
    """Update the caller's Alarm, notification, and time-zone preferences."""
    updated = update_settings(
        user=user,
        alarm_enabled=payload.alarm_enabled,
        notifications_enabled=payload.notifications_enabled,
        time_zone=payload.time_zone,
        user_repository=user_repository,
    )
    return _settings_response(updated)
