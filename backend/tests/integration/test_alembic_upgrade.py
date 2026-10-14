"""Integration tests: `alembic upgrade head` builds the schema from empty (T19, ADR-0002).

Proves the full migration chain on both engines the app supports: a fresh SQLite file (always
runs — no external service) and real PostgreSQL via `DATABASE_URL` (skips cleanly when that is
not set). Reuses `run_alembic_upgrade_head` from `conftest.py`, the same helper the PostgreSQL
constraint tests use to build their schema, so there is exactly one code path that drives
Alembic in this suite.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from sqlalchemy import create_engine, inspect, text
from tests.integration.conftest import run_alembic_downgrade, run_alembic_upgrade_head

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Connection, Engine

pytestmark = pytest.mark.integration

_EXPECTED_TABLES = frozenset(
    {"user", "auth_session", "task", "tag", "task_tags", "pomodoro", "timer"}
)

_USER_A, _USER_B = (UUID(int=i).hex for i in (1, 2))

# User A: created_at order contradicts name_key order, and the never-tagged Tag sorts last
# although its name sorts first. User B: nine Tags force the palette to wrap; none is carried by
# a Task, so they fall back to name_key order.
_USER_A_TAGS = (("alpha", "2026-03-01"), ("beta", "2026-02-01"), ("a_unused", None))
_USER_B_TAGS = tuple((f"t{n}", None) for n in range(1, 10))
_EXPECTED_COLORS = {
    "beta": "rose",
    "alpha": "orange",
    "a_unused": "amber",
    "t1": "rose",
    "t2": "orange",
    "t3": "amber",
    "t4": "green",
    "t5": "teal",
    "t6": "sky",
    "t7": "violet",
    "t8": "slate",
    "t9": "rose",
}


def _table_names(database_url: str) -> set[str]:
    engine: Engine = create_engine(database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_alembic_upgrade_head_builds_the_schema_on_a_fresh_sqlite_file(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'pomodoro.db'}"

    run_alembic_upgrade_head(database_url)

    assert _table_names(database_url) >= _EXPECTED_TABLES


def test_alembic_upgrade_head_builds_the_schema_on_a_fresh_postgresql_database() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("no PostgreSQL DATABASE_URL set")

    run_alembic_upgrade_head(database_url)

    assert _table_names(database_url) >= _EXPECTED_TABLES


def _insert_tags(conn: Connection) -> None:
    """Insert both Users' Tags; a Tag with a date is carried by a Task created on that date."""
    for user_id, tags in ((_USER_A, _USER_A_TAGS), (_USER_B, _USER_B_TAGS)):
        for index, (key, task_date) in enumerate(tags):
            tag_id = UUID(int=1000 + int(user_id, 16) * 100 + index).hex
            conn.execute(
                text("INSERT INTO tag (id, user_id, name, name_key) VALUES (:i, :u, :k, :k)"),
                {"i": tag_id, "u": user_id, "k": key},
            )
            if task_date is None:
                continue
            task_id = UUID(int=2000 + index).hex
            conn.execute(
                text(
                    "INSERT INTO task (id, user_id, text, text_key, position, created_at) "
                    "VALUES (:i, :u, :k, :k, :p, :d)"
                ),
                {"i": task_id, "u": user_id, "k": key, "p": index, "d": f"{task_date} 00:00:00"},
            )
            conn.execute(
                text("INSERT INTO task_tags (task_id, tag_id) VALUES (:t, :g)"),
                {"t": task_id, "g": tag_id},
            )


def _backfilled_colors(database_url: str) -> list[tuple[str, str]]:
    """Build a schema at 0008 with two Users' Tags, migrate to 0009, return pairs."""
    run_alembic_upgrade_head(database_url)
    run_alembic_downgrade(database_url, "0008")
    engine: Engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            for user_id, email in ((_USER_A, "a@x.com"), (_USER_B, "b@x.com")):
                conn.execute(
                    text(
                        'INSERT INTO "user" (id, email, email_key, password_hash, time_zone, '
                        "alarm_enabled, notifications_enabled, created_at) "
                        "VALUES (:id, :e, :e, 'x', 'UTC', true, false, '2026-01-01 00:00:00')"
                    ),
                    {"id": user_id, "e": email},
                )
            _insert_tags(conn)
        run_alembic_upgrade_head(database_url, "0009")
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT name_key, color FROM tag")).fetchall()
            conn.execute(
                text('DELETE FROM "user" WHERE id IN (:a, :b)'), {"a": _USER_A, "b": _USER_B}
            )
        return [(name_key, color) for name_key, color in rows]
    finally:
        engine.dispose()


def test_0009_backfills_palette_per_user_on_sqlite(tmp_path: Path) -> None:
    colors = _backfilled_colors(f"sqlite:///{tmp_path / 'pomodoro.db'}")

    assert dict(colors) == _EXPECTED_COLORS


def test_0009_backfills_palette_per_user_on_postgresql() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("no PostgreSQL DATABASE_URL set")

    colors = _backfilled_colors(database_url)

    assert dict(colors) == _EXPECTED_COLORS
