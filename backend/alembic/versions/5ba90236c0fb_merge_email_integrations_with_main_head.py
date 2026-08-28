"""merge_email_integrations_with_main_head

Revision ID: 5ba90236c0fb
Revises: 3323dd683332, 89a5593a5836
Create Date: 2026-08-28 14:09:34.828381

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '5ba90236c0fb'
down_revision: Union[str, None] = ('3323dd683332', '89a5593a5836')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
