"""pomodoro table (minimal prerequisite for T7's delete-block rule; full domain lands in T11).

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09 23:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the `pomodoro` table (ADR-0002) with its status/duration/time-order CHECKs."""
    op.create_table(
        "pomodoro",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_pomodoro"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_pomodoro_user_id_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["task.id"], name="fk_pomodoro_task_id_task", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("duration_seconds > 0", name="ck_pomodoro_duration_seconds_positive"),
        sa.CheckConstraint(
            "status IN ('completed', 'interrupted_logged')", name="ck_pomodoro_status"
        ),
        sa.CheckConstraint("ended_at >= started_at", name="ck_pomodoro_ended_at_after_started_at"),
    )
    op.create_index("ix_pomodoro_user_id", "pomodoro", ["user_id"])
    op.create_index("ix_pomodoro_task_id", "pomodoro", ["task_id"])
    op.create_index("ix_pomodoro_user_id_ended_at", "pomodoro", ["user_id", "ended_at"])


def downgrade() -> None:
    """Drop `pomodoro` and its indexes."""
    op.drop_index("ix_pomodoro_user_id_ended_at", table_name="pomodoro")
    op.drop_index("ix_pomodoro_task_id", table_name="pomodoro")
    op.drop_index("ix_pomodoro_user_id", table_name="pomodoro")
    op.drop_table("pomodoro")
