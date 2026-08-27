"""add_zoho_and_accounting_tables

Revision ID: 005_add_zoho_and_accounting_tables
Revises: 004_add_stage3_accounting_fields
Create Date: 2026-08-27 15:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005_add_zoho_and_accounting_tables"
down_revision: Union[str, None] = "004_add_stage3_accounting_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
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
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # Insert default tenant
    op.execute(
        "INSERT INTO tenants (id, name, slug) VALUES ('default-tenant-001', 'Default Organization', 'default-org') ON CONFLICT DO NOTHING"
    )

    # 2. Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="FINANCE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # 3. Create zoho_connections table
    op.create_table(
        "zoho_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(length=100), nullable=True),
        sa.Column("organization_name", sa.String(length=255), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("api_domain", sa.String(length=255), nullable=False, server_default="https://www.zohoapis.in"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="DISCONNECTED"),
        sa.Column("error_message", sa.Text(), nullable=True),
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
    op.create_index("ix_zoho_connections_tenant_id", "zoho_connections", ["tenant_id"], unique=True)

    # 4. Create chart_of_accounts table
    op.create_table(
        "chart_of_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zoho_account_id", sa.String(length=100), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("account_code", sa.String(length=50), nullable=True),
        sa.Column("account_type", sa.String(length=50), nullable=False, server_default="expense"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
    op.create_index("ix_chart_of_accounts_tenant_id", "chart_of_accounts", ["tenant_id"])
    op.create_index("ix_chart_of_accounts_zoho_account_id", "chart_of_accounts", ["zoho_account_id"])

    # 5. Create tax_rates table
    op.create_table(
        "tax_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zoho_tax_id", sa.String(length=100), nullable=False),
        sa.Column("tax_name", sa.String(length=255), nullable=False),
        sa.Column("tax_percentage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tax_type", sa.String(length=50), nullable=False, server_default="GST"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
    op.create_index("ix_tax_rates_tenant_id", "tax_rates", ["tenant_id"])
    op.create_index("ix_tax_rates_zoho_tax_id", "tax_rates", ["zoho_tax_id"])

    # 6. Create vendors table
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("zoho_contact_id", sa.String(length=100), nullable=True),
        sa.Column("vendor_name", sa.String(length=255), nullable=False),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("pan", sa.String(length=10), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("approval_status", sa.String(length=50), nullable=False, server_default="APPROVED"),
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
    op.create_index("ix_vendors_tenant_id", "vendors", ["tenant_id"])
    op.create_index("ix_vendors_zoho_contact_id", "vendors", ["zoho_contact_id"])
    op.create_index("ix_vendors_gstin", "vendors", ["gstin"])
    op.create_index("ix_vendors_pan", "vendors", ["pan"])

    # 7. Add enterprise columns to invoices table
    op.add_column("invoices", sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default-tenant-001"))
    op.add_column("invoices", sa.Column("invoice_type", sa.String(length=50), nullable=False, server_default="VENDOR_INVOICE"))
    op.add_column("invoices", sa.Column("approval_status", sa.String(length=50), nullable=False, server_default="PENDING_REVIEW"))
    op.add_column("invoices", sa.Column("export_status", sa.String(length=50), nullable=False, server_default="NOT_EXPORTED"))
    op.add_column("invoices", sa.Column("zoho_bill_id", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("zoho_bill_number", sa.String(length=100), nullable=True))
    op.add_column("invoices", sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    
    op.create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])
    op.create_index("ix_invoices_zoho_bill_id", "invoices", ["zoho_bill_id"])

    # 8. Create journal_entries table
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default-tenant-001"),
        sa.Column("entry_date", sa.String(length=50), nullable=True),
        sa.Column("total_debit", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_credit", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("is_balanced", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="DRAFT"),
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
    op.create_index("ix_journal_entries_invoice_id", "journal_entries", ["invoice_id"], unique=True)
    op.create_index("ix_journal_entries_tenant_id", "journal_entries", ["tenant_id"])

    # 9. Create journal_lines table
    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(length=100), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("line_type", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cost_center", sa.String(length=100), nullable=True),
        sa.Column("project", sa.String(length=100), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_journal_lines_journal_entry_id", "journal_lines", ["journal_entry_id"])

    # 10. Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="default-tenant-001"),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_invoice_id", "audit_logs", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    
    op.drop_index("ix_invoices_zoho_bill_id", table_name="invoices")
    op.drop_index("ix_invoices_tenant_id", table_name="invoices")
    op.drop_column("invoices", "locked_at")
    op.drop_column("invoices", "exported_at")
    op.drop_column("invoices", "zoho_bill_number")
    op.drop_column("invoices", "zoho_bill_id")
    op.drop_column("invoices", "export_status")
    op.drop_column("invoices", "approval_status")
    op.drop_column("invoices", "invoice_type")
    op.drop_column("invoices", "tenant_id")
    
    op.drop_table("vendors")
    op.drop_table("tax_rates")
    op.drop_table("chart_of_accounts")
    op.drop_table("zoho_connections")
    op.drop_table("users")
    op.drop_table("tenants")
