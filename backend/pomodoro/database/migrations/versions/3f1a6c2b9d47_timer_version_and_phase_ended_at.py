"""Timer: add version (CAS) and phase_ended_at columns.

Revision ID: 3f1a6c2b9d47
Revises: 9c8f6e5130a9
Create Date: 2026-10-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from pomodoro.database.types import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "3f1a6c2b9d47"
down_revision: str | Sequence[str] | None = "9c8f6e5130a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("timer", sa.Column("phase_ended_at", UTCDateTime(timezone=True), nullable=True))
    op.add_column(
        "timer",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("timer", "version")
    op.drop_column("timer", "phase_ended_at")
