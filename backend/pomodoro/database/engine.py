"""SQLAlchemy/SQLModel engine construction.

Takes a plain connection-string argument rather than reading settings itself:
`database` sits below `entrypoints` in the import-linter layer contract (CES-5),
so it must never import `pomodoro.entrypoints.settings`. Callers in entrypoints
pass `get_settings().database_url` in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import create_engine

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


def build_engine(database_url: str) -> Engine:
    """Create an engine for `database_url` (SQLite locally, PostgreSQL in prod, ADR-0002)."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)
