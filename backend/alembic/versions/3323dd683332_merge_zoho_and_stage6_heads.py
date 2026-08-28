"""merge_zoho_and_stage6_heads

Revision ID: 3323dd683332
Revises: 005_add_zoho_and_accounting_tables, 007_add_stage6_journal_tables
Create Date: 2026-08-28 13:17:36.685949

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '3323dd683332'
down_revision: Union[str, None] = ('005_add_zoho_and_accounting_tables', '007_add_stage6_journal_tables')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
