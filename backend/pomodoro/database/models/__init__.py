"""SQLModel tables. Importing this package registers every one on `SQLModel.metadata`."""

from __future__ import annotations

from pomodoro.database.models.auth_session import AuthSessionTable
from pomodoro.database.models.pomodoro import PomodoroTable
from pomodoro.database.models.tag import TagTable
from pomodoro.database.models.task import TaskTable
from pomodoro.database.models.task_tag import TaskTagTable
from pomodoro.database.models.timer import TimerTable
from pomodoro.database.models.user import UserTable

__all__ = [
    "AuthSessionTable",
    "PomodoroTable",
    "TagTable",
    "TaskTable",
    "TaskTagTable",
    "TimerTable",
    "UserTable",
]
