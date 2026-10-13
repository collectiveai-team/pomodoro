"""timer table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09 01:00:00.000000

The full `pomodoro` definition already exists in T7's 0004 migration. This revision adds only
the persisted live Timer table; it deliberately does not recreate or alter `pomodoro`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the one-row-per-User Timer table used by lazy settlement."""
    op.create_table(
        "timer",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("break_kind", sa.String(), nullable=True),
        sa.Column("phase_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accumulated_active_seconds", sa.Integer(), nullable=False),
        sa.Column("running_since", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id", name="pk_timer"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_timer_user_id_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["task.id"], name="fk_timer_task_id_task", ondelete="RESTRICT"
        ),
    )


def downgrade() -> None:
    """Drop the Timer table without touching the pre-existing Pomodoro table."""
    op.drop_table("timer")
