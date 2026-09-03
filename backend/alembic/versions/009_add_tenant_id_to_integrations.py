"""add_tenant_id_to_integrations

Revision ID: 009_integrations_tenant_id
Revises: 008_period_controls
Create Date: 2026-09-04 00:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '009_integrations_tenant_id'
down_revision: Union[str, None] = '008_period_controls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    integration_cols = {col["name"] for col in inspector.get_columns("integrations")}
    if "tenant_id" not in integration_cols:
        op.add_column(
            "integrations",
            sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default-tenant-001"),
        )
        op.create_index(
            op.f("ix_integrations_tenant_id"),
            "integrations",
            ["tenant_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    integration_cols = {col["name"] for col in inspector.get_columns("integrations")}
    if "tenant_id" in integration_cols:
        op.drop_index(op.f("ix_integrations_tenant_id"), table_name="integrations")
        op.drop_column("integrations", "tenant_id")
