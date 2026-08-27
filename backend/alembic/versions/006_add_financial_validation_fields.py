"""add_financial_validation_fields

Revision ID: 006_add_financial_validation_fields
Revises: 005_add_stage4_gst_itc_fields
Create Date: 2026-08-27 16:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006_add_financial_validation_fields"
down_revision: Union[str, None] = "005_add_stage4_gst_itc_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "financial_validation_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "financial_validation_result")
