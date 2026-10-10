"""allow zero-duration logged interruptions.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-10 00:45:00.000000

Story 52 permits logging an interruption with no active seconds.  This forward migration
replaces the historical positive-duration CHECK without weakening the status or timestamp
integrity CHECKs created in revision 0004.
"""

from __future__ import annotations

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Replace the positive duration CHECK with a portable non-negative one."""
    with op.batch_alter_table("pomodoro") as batch_op:
        batch_op.drop_constraint("ck_pomodoro_duration_seconds_positive", type_="check")
        batch_op.create_check_constraint(
            "ck_pomodoro_duration_seconds_nonnegative", "duration_seconds >= 0"
        )


def downgrade() -> None:
    """Restore the prior positive duration CHECK."""
    with op.batch_alter_table("pomodoro") as batch_op:
        batch_op.drop_constraint("ck_pomodoro_duration_seconds_nonnegative", type_="check")
        batch_op.create_check_constraint(
            "ck_pomodoro_duration_seconds_positive", "duration_seconds > 0"
        )
