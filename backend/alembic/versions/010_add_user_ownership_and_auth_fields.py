"""add_user_ownership_and_auth_fields

Revision ID: 010_user_ownership_auth
Revises: 009_integrations_tenant_id
Create Date: 2026-09-04 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '010_user_ownership_auth'
down_revision: Union[str, None] = '009_integrations_tenant_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. users: password_hash
    if "users" in inspector.get_table_names():
        user_cols = {col["name"] for col in inspector.get_columns("users")}
        if "password_hash" not in user_cols:
            op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))

    # 2. invoices: owner_user_id
    if "invoices" in inspector.get_table_names():
        inv_cols = {col["name"] for col in inspector.get_columns("invoices")}
        if "owner_user_id" not in inv_cols:
            op.add_column(
                "invoices",
                sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            )
            op.create_index(op.f("ix_invoices_owner_user_id"), "invoices", ["owner_user_id"], unique=False)

    # 3. zoho_connections: user_id & constraints
    if "zoho_connections" in inspector.get_table_names():
        zoho_cols = {col["name"] for col in inspector.get_columns("zoho_connections")}
        if "user_id" not in zoho_cols:
            op.add_column(
                "zoho_connections",
                sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            )
            op.create_index(op.f("ix_zoho_connections_user_id"), "zoho_connections", ["user_id"], unique=False)

    # 4. integrations: user_id
    if "integrations" in inspector.get_table_names():
        int_cols = {col["name"] for col in inspector.get_columns("integrations")}
        if "user_id" not in int_cols:
            op.add_column(
                "integrations",
                sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            )
            op.create_index(op.f("ix_integrations_user_id"), "integrations", ["user_id"], unique=False)

    # 5. hitl_reviews: tenant_id, user_id
    if "hitl_reviews" in inspector.get_table_names():
        hitl_cols = {col["name"] for col in inspector.get_columns("hitl_reviews")}
        if "tenant_id" not in hitl_cols:
            op.add_column("hitl_reviews", sa.Column("tenant_id", sa.String(length=64), nullable=True))
            op.create_index(op.f("ix_hitl_reviews_tenant_id"), "hitl_reviews", ["tenant_id"], unique=False)
        if "user_id" not in hitl_cols:
            op.add_column(
                "hitl_reviews",
                sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            )
            op.create_index(op.f("ix_hitl_reviews_user_id"), "hitl_reviews", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "hitl_reviews" in inspector.get_table_names():
        hitl_cols = {col["name"] for col in inspector.get_columns("hitl_reviews")}
        if "user_id" in hitl_cols:
            op.drop_index(op.f("ix_hitl_reviews_user_id"), table_name="hitl_reviews")
            op.drop_column("hitl_reviews", "user_id")
        if "tenant_id" in hitl_cols:
            op.drop_index(op.f("ix_hitl_reviews_tenant_id"), table_name="hitl_reviews")
            op.drop_column("hitl_reviews", "tenant_id")

    if "integrations" in inspector.get_table_names():
        int_cols = {col["name"] for col in inspector.get_columns("integrations")}
        if "user_id" in int_cols:
            op.drop_index(op.f("ix_integrations_user_id"), table_name="integrations")
            op.drop_column("integrations", "user_id")

    if "zoho_connections" in inspector.get_table_names():
        zoho_cols = {col["name"] for col in inspector.get_columns("zoho_connections")}
        if "user_id" in zoho_cols:
            op.drop_index(op.f("ix_zoho_connections_user_id"), table_name="zoho_connections")
            op.drop_column("zoho_connections", "user_id")

    if "invoices" in inspector.get_table_names():
        inv_cols = {col["name"] for col in inspector.get_columns("invoices")}
        if "owner_user_id" in inv_cols:
            op.drop_index(op.f("ix_invoices_owner_user_id"), table_name="invoices")
            op.drop_column("invoices", "owner_user_id")

    if "users" in inspector.get_table_names():
        user_cols = {col["name"] for col in inspector.get_columns("users")}
        if "password_hash" in user_cols:
            op.drop_column("users", "password_hash")
