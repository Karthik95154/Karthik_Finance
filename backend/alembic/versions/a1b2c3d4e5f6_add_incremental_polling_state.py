"""add_incremental_polling_state_to_email_connections

Revision ID: a1b2c3d4e5f6
Revises: 3ad6b6cbe86b
Create Date: 2026-09-07 10:00:00.000000

Adds three columns to email_connections to support incremental email polling:
  last_successful_poll_at  - UTC timestamp of last successful poll (NULL = never polled)
  automatic_polling_enabled - Enables 7AM daily auto-poll after first manual poll succeeds
  is_polling               - Concurrent-poll mutex flag
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3ad6b6cbe86b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("email_connections")}

    if "last_successful_poll_at" not in existing_cols:
        op.add_column("email_connections", sa.Column("last_successful_poll_at", sa.DateTime(timezone=True), nullable=True))

    if "automatic_polling_enabled" not in existing_cols:
        op.add_column("email_connections", sa.Column("automatic_polling_enabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")))

    if "is_polling" not in existing_cols:
        op.add_column("email_connections", sa.Column("is_polling", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("email_connections")}

    if "is_polling" in existing_cols:
        op.drop_column("email_connections", "is_polling")
    if "automatic_polling_enabled" in existing_cols:
        op.drop_column("email_connections", "automatic_polling_enabled")
    if "last_successful_poll_at" in existing_cols:
        op.drop_column("email_connections", "last_successful_poll_at")
