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
    alarm_enabled: bool,
    notifications_enabled: bool,
    time_zone: str,
    user_repository: UserRepository,
) -> User:
    """Validate `time_zone` and persist the caller's preferences, returning the updated User."""
    validate_time_zone(time_zone)
    user_repository.update_preferences(
        user.id,
        alarm_enabled=alarm_enabled,
        notifications_enabled=notifications_enabled,
        time_zone=time_zone,
    )

    log.info("settings_updated", user_id=str(user.id))
    return replace(
        user,
        alarm_enabled=alarm_enabled,
        notifications_enabled=notifications_enabled,
        time_zone=time_zone,
    )
