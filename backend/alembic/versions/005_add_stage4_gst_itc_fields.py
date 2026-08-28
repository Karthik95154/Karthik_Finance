"""add_stage4_gst_itc_fields placeholder

Revision ID: 005_add_stage4_gst_itc_fields
Revises: 004_add_stage3_accounting_fields
Create Date: 2026-08-27 08:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "005_add_stage4_gst_itc_fields"
down_revision: Union[str, None] = "004_add_stage3_accounting_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Placeholder for database migration 005 that is already executed on database
    pass


def downgrade() -> None:
    pass
