"""Persistence: SQLModel tables, Alembic migrations and repositories.

Only this package may import SQLModel table classes or Alembic internals;
callers in `api`/`entrypoints` use the engine/session factory exported here.
"""

from pomodoro.database.engine import DEFAULT_DATABASE_URL, create_db_engine, session_scope

__all__ = ["DEFAULT_DATABASE_URL", "create_db_engine", "session_scope"]
