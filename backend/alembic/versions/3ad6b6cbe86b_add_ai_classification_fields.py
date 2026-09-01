"""add_ai_classification_fields

Revision ID: 3ad6b6cbe86b
Revises: 5ba90236c0fb
Create Date: 2026-09-01 11:50:05.220823

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '3ad6b6cbe86b'
down_revision: Union[str, None] = '5ba90236c0fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("invoices")}

    # Add missing classification fields strictly if they do not exist
    if "financial_relevance" not in existing_cols:
        op.add_column("invoices", sa.Column("financial_relevance", sa.String(length=50), nullable=True))
        op.create_index(op.f("ix_invoices_financial_relevance"), "invoices", ["financial_relevance"], unique=False)
    
    if "document_type" not in existing_cols:
        op.add_column("invoices", sa.Column("document_type", sa.String(length=50), nullable=True))
        op.create_index(op.f("ix_invoices_document_type"), "invoices", ["document_type"], unique=False)

    if "classification_confidence" not in existing_cols:
        op.add_column("invoices", sa.Column("classification_confidence", sa.Float(), nullable=True))

    if "classification_reason" not in existing_cols:
        op.add_column("invoices", sa.Column("classification_reason", sa.Text(), nullable=True))

    if "classification_model" not in existing_cols:
        op.add_column("invoices", sa.Column("classification_model", sa.String(length=100), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("invoices")}

    if "classification_model" in existing_cols:
        op.drop_column("invoices", "classification_model")

    if "classification_reason" in existing_cols:
        op.drop_column("invoices", "classification_reason")

    if "classification_confidence" in existing_cols:
        op.drop_column("invoices", "classification_confidence")

