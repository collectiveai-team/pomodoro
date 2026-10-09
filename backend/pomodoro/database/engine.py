"""SQLAlchemy/SQLModel engine construction.

Takes a plain connection-string argument rather than reading settings itself:
`database` sits below `entrypoints` in the import-linter layer contract (CES-5),
so it must never import `pomodoro.entrypoints.settings`. Callers in entrypoints
pass `get_settings().database_url` in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlmodel import create_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def build_engine(database_url: str) -> Engine:
    """Create an engine for `database_url` (SQLite locally, PostgreSQL in prod, ADR-0002)."""
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(database_url, connect_args=connect_args)
    if is_sqlite:
        _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ignores FK constraints unless `PRAGMA foreign_keys=ON` runs per connection."""

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
