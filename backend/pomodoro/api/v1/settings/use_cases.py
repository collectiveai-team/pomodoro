"""Settings use case: validate and persist a User's preferences (T15).

Reading Settings needs no use case of its own — `routers.py` renders the already-resolved
`User` from `get_current_user` directly, the same way `auth.routers.me` does.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from pomodoro.core.logger import get_logger
from pomodoro.core.users import User, validate_time_zone

if TYPE_CHECKING:
    from pomodoro.core.users import UserRepository

log = get_logger(__name__)


def update_settings(
    *,
    user: User,
    alarm_enabled: bool | None,
    notifications_enabled: bool | None,
    time_zone: str | None,
    user_repository: UserRepository,
) -> User:
    """Merge the sent preferences over the stored ones and persist them, returning the User.

    `None` means "not sent": the stored value is kept. A sent `time_zone` is validated first.
    """
    if time_zone is not None:
        validate_time_zone(time_zone)
    updated = replace(
        user,
        alarm_enabled=user.alarm_enabled if alarm_enabled is None else alarm_enabled,
        notifications_enabled=(
            user.notifications_enabled if notifications_enabled is None else notifications_enabled
        ),
        time_zone=user.time_zone if time_zone is None else time_zone,
    )
    user_repository.update_preferences(
        user.id,
        alarm_enabled=updated.alarm_enabled,
        notifications_enabled=updated.notifications_enabled,
        time_zone=updated.time_zone,
    )

    log.info("settings_updated", user_id=str(user.id))
    return updated
