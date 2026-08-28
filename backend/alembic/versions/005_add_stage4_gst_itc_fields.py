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
    # gst_result and itc_result columns are already applied on the live database.
    # This migration is a no-op to avoid duplicate column errors on re-run.
    pass


def downgrade() -> None:
    op.drop_column("invoices", "itc_result")
    op.drop_column("invoices", "gst_result")
