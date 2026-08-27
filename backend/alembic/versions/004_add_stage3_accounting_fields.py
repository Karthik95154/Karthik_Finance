"""add_stage3_accounting_fields

Revision ID: 004_add_stage3_accounting_fields
Revises: 003_add_current_vlm_output
Create Date: 2026-08-27 07:44:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004_add_stage3_accounting_fields"
down_revision: Union[str, None] = "003_add_current_vlm_output"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column(
            "accounting_output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "current_accounting_output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "accounting_confidence",
            sa.Float(),
            nullable=True,
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "accounting_status",
            sa.String(length=50),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "accounting_status")
    op.drop_column("invoices", "accounting_confidence")
    op.drop_column("invoices", "current_accounting_output")
    op.drop_column("invoices", "accounting_output")
