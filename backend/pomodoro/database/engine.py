"""SQLAlchemy/SQLModel engine construction.

Takes a plain connection-string argument rather than reading settings itself:
`database` sits below `entrypoints` in the import-linter layer contract (CES-5),
so it must never import `pomodoro.entrypoints.settings`. Callers in entrypoints
pass `get_settings().database_url` in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

_SQLITE_MEMORY_URLS = frozenset({"sqlite://", "sqlite:///:memory:"})


def build_engine(database_url: str) -> Engine:
    """Create an engine for `database_url` (SQLite locally, PostgreSQL in prod, ADR-0002)."""
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine_kwargs: dict[str, Any] = {"connect_args": connect_args}
    if database_url in _SQLITE_MEMORY_URLS:
        # A plain `:memory:` sqlite connection is private to the thread that opened it, so
        # a session opened from FastAPI's request-handling thread pool (T8's `require_session`,
        # resolved via TestClient) would otherwise see an empty, unrelated database from the
        # one a test's fixtures set up on the main thread. `StaticPool` keeps exactly one
        # connection alive and shares it across every thread, which is the documented SQLAlchemy
        # pattern for an in-memory SQLite database used from more than one thread.
        engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **engine_kwargs)
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
