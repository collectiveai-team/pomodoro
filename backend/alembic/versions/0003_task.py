"""task table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09 22:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None

_ACTIVE_TEXT_KEY_WHERE = sa.text("archived_at IS NULL")


def upgrade() -> None:
    """Create the `task` table with its per-User, Active-only unique text index (ADR-0002)."""
    op.create_table(
        "task",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("text_key", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_task"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_task_user_id_user", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_task_user_id", "task", ["user_id"])
    op.create_index(
        "ix_task_user_id_text_key_active",
        "task",
        ["user_id", "text_key"],
        unique=True,
        sqlite_where=_ACTIVE_TEXT_KEY_WHERE,
        postgresql_where=_ACTIVE_TEXT_KEY_WHERE,
    )


def downgrade() -> None:
    """Drop `task` and its indexes."""
    op.drop_index("ix_task_user_id_text_key_active", table_name="task")
    op.drop_index("ix_task_user_id", table_name="task")
    op.drop_table("task")
