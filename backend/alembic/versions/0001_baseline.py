"""baseline.

Revision ID: 0001
Revises:
Create Date: 2026-10-09 18:18:40.189977
"""

from __future__ import annotations

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Empty baseline: establishes `alembic_version` with no schema yet."""


def downgrade() -> None:
    """Empty baseline: nothing to undo."""
