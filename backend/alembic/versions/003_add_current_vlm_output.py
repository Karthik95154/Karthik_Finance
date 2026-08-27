"""add_current_vlm_output

Revision ID: 003_add_current_vlm_output
Revises: 002_add_vlm_stage2_fields
Create Date: 2026-08-27 07:12:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_add_current_vlm_output"
down_revision: Union[str, None] = "002_add_vlm_stage2_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "current_vlm_output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "current_vlm_output")
