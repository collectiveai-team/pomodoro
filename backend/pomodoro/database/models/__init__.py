"""SQLModel tables. Importing this package registers every one on `SQLModel.metadata`."""

from __future__ import annotations

from pomodoro.database.models.auth_session import AuthSessionTable
from pomodoro.database.models.task import TaskTable
from pomodoro.database.models.user import UserTable

__all__ = ["AuthSessionTable", "TaskTable", "UserTable"]
