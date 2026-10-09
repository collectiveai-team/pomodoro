"""CES-18 · the database layer's SQLAlchemy engine (ADR-0002).

Builds the engine from the `database_url` setting (read via the CES-76 settings module, never
`os.environ` here). The same code path works for both the local SQLite default and a PostgreSQL
`DATABASE_URL` in production. SQLite does not enforce foreign keys by default, so every SQLite
DBAPI connection gets `PRAGMA foreign_keys = ON`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url

from pomodoro.settings import get_settings

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

_SQLITE_DRIVERNAME_PREFIX = "sqlite"


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def _ensure_sqlite_file_directory_exists(url: URL) -> None:
    database = url.database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)


def build_engine(database_url: str | None = None) -> Engine:
    """Build a SQLAlchemy engine for `database_url` (default: the settings module's)."""
    url = make_url(database_url if database_url is not None else get_settings().database_url)
    is_sqlite = url.drivername.startswith(_SQLITE_DRIVERNAME_PREFIX)
    if is_sqlite:
        _ensure_sqlite_file_directory_exists(url)

    engine = create_engine(url)
    if is_sqlite:
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide engine, built once from settings."""
    return build_engine()
