"""add_vlm_stage2_fields

Revision ID: 002_add_vlm_stage2_fields
Revises: 001_create_invoices
Create Date: 2026-08-27 06:36:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_add_vlm_stage2_fields"
down_revision: Union[str, None] = "001_create_invoices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column("invoices", sa.Column("raw_vlm_output", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "raw_vlm_output")
    op.drop_column("invoices", "confidence_score")
    op.drop_column("invoices", "error_message")
