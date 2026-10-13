"""tag and task_tags tables (T8): User-scoped Tags and their Task assignments.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create `tag` (unique per User by `name_key`) and `task_tags` (cascading join table)."""
    op.create_table(
        "tag",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tag"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_tag_user_id_user", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_tag_user_id", "tag", ["user_id"])
    op.create_index("ix_tag_user_id_name_key", "tag", ["user_id", "name_key"], unique=True)

    op.create_table(
        "task_tags",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("task_id", "tag_id", name="pk_task_tags"),
        sa.ForeignKeyConstraint(
            ["task_id"], ["task.id"], name="fk_task_tags_task_id_task", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tag.id"], name="fk_task_tags_tag_id_tag", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_task_tags_tag_id", "task_tags", ["tag_id"])


def downgrade() -> None:
    """Drop `task_tags` and `tag` and their indexes."""
    op.drop_index("ix_task_tags_tag_id", table_name="task_tags")
    op.drop_table("task_tags")
    op.drop_index("ix_tag_user_id_name_key", table_name="tag")
    op.drop_index("ix_tag_user_id", table_name="tag")
    op.drop_table("tag")
