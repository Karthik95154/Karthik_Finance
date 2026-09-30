"""add_closed_accounting_period_controls

Revision ID: 008_period_controls
Revises: 3ad6b6cbe86b
Create Date: 2026-09-03 21:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '008_period_controls'
down_revision: Union[str, None] = '3ad6b6cbe86b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Update tenants table
    tenant_cols = {col["name"] for col in inspector.get_columns("tenants")}
    if "books_closed_through_date" not in tenant_cols:
        op.add_column("tenants", sa.Column("books_closed_through_date", sa.Date(), nullable=True))

    # 2. Update invoices table
    invoice_cols = {col["name"] for col in inspector.get_columns("invoices")}
    if "posting_date" not in invoice_cols:
        op.add_column("invoices", sa.Column("posting_date", sa.Date(), nullable=True))
        op.create_index(op.f("ix_invoices_posting_date"), "invoices", ["posting_date"], unique=False)

    if "period_resolution" not in invoice_cols:
        op.add_column("invoices", sa.Column("period_resolution", sa.String(length=50), nullable=False, server_default="NONE"))
        op.create_index(op.f("ix_invoices_period_resolution"), "invoices", ["period_resolution"], unique=False)

    if "period_resolution_reason" not in invoice_cols:
        op.add_column("invoices", sa.Column("period_resolution_reason", sa.Text(), nullable=True))

    if "period_resolved_by" not in invoice_cols:
        op.add_column("invoices", sa.Column("period_resolved_by", sa.String(length=255), nullable=True))

    if "period_resolved_at" not in invoice_cols:
        op.add_column("invoices", sa.Column("period_resolved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    invoice_cols = {col["name"] for col in inspector.get_columns("invoices")}
    if "period_resolved_at" in invoice_cols:
        op.drop_column("invoices", "period_resolved_at")
    if "period_resolved_by" in invoice_cols:
        op.drop_column("invoices", "period_resolved_by")
    if "period_resolution_reason" in invoice_cols:
        op.drop_column("invoices", "period_resolution_reason")
    if "period_resolution" in invoice_cols:
        op.drop_index(op.f("ix_invoices_period_resolution"), table_name="invoices")
        op.drop_column("invoices", "period_resolution")
    if "posting_date" in invoice_cols:
        op.drop_index(op.f("ix_invoices_posting_date"), table_name="invoices")
        op.drop_column("invoices", "posting_date")

    tenant_cols = {col["name"] for col in inspector.get_columns("tenants")}
    if "books_closed_through_date" in tenant_cols:
        op.drop_column("tenants", "books_closed_through_date")
