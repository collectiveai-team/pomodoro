"""restore the positive duration CHECK on pomodoro.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-10 02:00:00.000000

A 0 s interruption is treated as a discard (spec Further Notes), so no Pomodoro is ever
persisted with `duration_seconds = 0`.  Rows written by the earlier behaviour are removed
before the original `duration_seconds > 0` CHECK is restored.
"""

from __future__ import annotations

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Drop zero-duration rows, then replace the non-negative CHECK with a positive one."""
    op.execute("DELETE FROM pomodoro WHERE duration_seconds = 0")
    with op.batch_alter_table("pomodoro") as batch_op:
        batch_op.drop_constraint("ck_pomodoro_duration_seconds_nonnegative", type_="check")
        batch_op.create_check_constraint(
            "ck_pomodoro_duration_seconds_positive", "duration_seconds > 0"
        )


def downgrade() -> None:
    """Relax the CHECK back to non-negative."""
    with op.batch_alter_table("pomodoro") as batch_op:
        batch_op.drop_constraint("ck_pomodoro_duration_seconds_positive", type_="check")
        batch_op.create_check_constraint(
            "ck_pomodoro_duration_seconds_nonnegative", "duration_seconds >= 0"
        )
