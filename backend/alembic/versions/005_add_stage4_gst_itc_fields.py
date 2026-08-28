"""add_stage4_gst_itc_fields

Revision ID: 005_add_stage4_gst_itc_fields
Revises: 004_add_stage3_accounting_fields
Create Date: 2026-08-27 14:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_add_stage4_gst_itc_fields"
down_revision: Union[str, None] = "004_add_stage3_accounting_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "gst_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "itc_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "itc_result")
    op.drop_column("invoices", "gst_result")
