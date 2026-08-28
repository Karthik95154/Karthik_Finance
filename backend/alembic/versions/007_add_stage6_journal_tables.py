"""add_stage6_journal_tables

Revision ID: 007_add_stage6_journal_tables
Revises: 006_add_financial_validation_fields
Create Date: 2026-08-27 17:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

revision: str = "007_add_stage6_journal_tables"
down_revision: Union[str, None] = "006_add_financial_validation_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # 1. Add journal_entry column to invoices if not present
    invoice_cols = [c["name"] for c in inspector.get_columns("invoices")]
    if "journal_entry" not in invoice_cols:
        op.add_column(
            "invoices",
            sa.Column(
                "journal_entry",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )

    # 2. Update/create journal_entries table
    tables = inspector.get_table_names()
    if "journal_entries" not in tables:
        op.create_table(
            "journal_entries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "invoice_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("invoices.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="BALANCED"),
            sa.Column("total_debit", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("total_credit", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("difference", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("balanced", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index("ix_journal_entries_invoice_id", "journal_entries", ["invoice_id"])
        op.create_index("ix_journal_entries_status", "journal_entries", ["status"])
    else:
        je_cols = [c["name"] for c in inspector.get_columns("journal_entries")]
        if "difference" not in je_cols:
            op.add_column("journal_entries", sa.Column("difference", sa.Float(), nullable=False, server_default="0.0"))
        if "balanced" not in je_cols:
            op.add_column("journal_entries", sa.Column("balanced", sa.Boolean(), nullable=False, server_default="true"))

    # 3. Update/create journal_lines table
    if "journal_lines" not in tables:
        op.create_table(
            "journal_lines",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "journal_entry_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("journal_entries.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("account_id", sa.String(length=100), nullable=False),
            sa.Column("account_name", sa.String(length=255), nullable=False),
            sa.Column("line_type", sa.String(length=50), nullable=False),
            sa.Column("debit", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("credit", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("source_line_index", sa.Integer(), nullable=True),
            sa.Column("provenance", sa.String(length=50), nullable=False, server_default="DETERMINISTIC"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index("ix_journal_lines_journal_entry_id", "journal_lines", ["journal_entry_id"])
    else:
        jl_cols = [c["name"] for c in inspector.get_columns("journal_lines")]
        if "debit" not in jl_cols:
            op.add_column("journal_lines", sa.Column("debit", sa.Float(), nullable=False, server_default="0.0"))
        if "credit" not in jl_cols:
            op.add_column("journal_lines", sa.Column("credit", sa.Float(), nullable=False, server_default="0.0"))
        if "source_line_index" not in jl_cols:
            op.add_column("journal_lines", sa.Column("source_line_index", sa.Integer(), nullable=True))
        if "provenance" not in jl_cols:
            op.add_column("journal_lines", sa.Column("provenance", sa.String(length=50), nullable=False, server_default="DETERMINISTIC"))
        if "created_at" not in jl_cols:
            op.add_column("journal_lines", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))


def downgrade() -> None:
    pass
