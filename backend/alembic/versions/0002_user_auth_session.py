"""user and auth_session tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-09 21:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the `user` and `auth_session` tables (ADR-0002 schema)."""
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("email_key", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("time_zone", sa.String(), nullable=False),
        sa.Column("alarm_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user"),
        sa.UniqueConstraint("email_key", name="uq_user_email_key"),
    )
    op.create_table(
        "auth_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_auth_session"),
        sa.UniqueConstraint("token_hash", name="uq_auth_session_token_hash"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_auth_session_user_id_user", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_auth_session_user_id", "auth_session", ["user_id"])


def downgrade() -> None:
    """Drop `auth_session` and `user`, in FK-safe order."""
    op.drop_index("ix_auth_session_user_id", table_name="auth_session")
    op.drop_table("auth_session")
    op.drop_table("user")
