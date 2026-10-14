"""tag.color: every Tag carries a palette color key.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-14 00:00:00.000000

The `tag` table has no creation timestamp, so the backfill orders each User's existing Tags by
the earliest `created_at` of a Task carrying them (Tags carried by no Task last), then by
`name_key` for determinism, and rotates the palette in that order.
"""

from __future__ import annotations

from collections import defaultdict

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None

# The closed palette, frozen here so the migration never drifts with the core enum.
_PALETTE = ("rose", "orange", "amber", "green", "teal", "sky", "violet", "slate")


def upgrade() -> None:
    """Add `color` nullable, backfill by rotating the palette per User, then make it NOT NULL."""
    op.add_column("tag", sa.Column("color", sa.String(), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT tag.id, tag.user_id, tag.name_key, MIN(task.created_at) AS first_used "
            "FROM tag "
            "LEFT JOIN task_tags ON task_tags.tag_id = tag.id "
            "LEFT JOIN task ON task.id = task_tags.task_id "
            "GROUP BY tag.id, tag.user_id, tag.name_key"
        )
    ).fetchall()
    by_user: dict[object, list[tuple[object, ...]]] = defaultdict(list)
    for row in rows:
        by_user[row[1]].append(tuple(row))
    for user_rows in by_user.values():
        user_rows.sort(key=lambda r: (r[3] is None, str(r[3] or ""), r[2]))
        for index, row in enumerate(user_rows):
            bind.execute(
                sa.text("UPDATE tag SET color = :color WHERE id = :id"),
                {"color": _PALETTE[index % len(_PALETTE)], "id": row[0]},
            )
    with op.batch_alter_table("tag") as batch_op:
        batch_op.alter_column("color", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    """Drop `tag.color`."""
    with op.batch_alter_table("tag") as batch_op:
        batch_op.drop_column("color")
