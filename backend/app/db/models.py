import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True)  # e.g. "default-tenant-001"
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    zoho_connection = relationship("ZohoConnection", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    chart_of_accounts = relationship("ChartOfAccount", back_populates="tenant", cascade="all, delete-orphan")
    tax_rates = relationship("TaxRate", back_populates="tenant", cascade="all, delete-orphan")
    vendors = relationship("Vendor", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="FINANCE")  # ADMIN, FINANCE, VIEWER
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship("Tenant", back_populates="users")


class ZohoConnection(Base):
    __tablename__ = "zoho_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    organization_id = Column(String(100), nullable=True)
    organization_name = Column(String(255), nullable=True)
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    api_domain = Column(String(255), nullable=False, default="https://www.zohoapis.in")
    status = Column(String(50), nullable=False, default="DISCONNECTED")  # CONNECTED, DISCONNECTED, ERROR
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship("Tenant", back_populates="zoho_connection")


# Alias for backward compatibility
ZohoCredential = ZohoConnection


class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zoho_account_id = Column(String(100), nullable=False, index=True)
    account_name = Column(String(255), nullable=False)
    account_code = Column(String(50), nullable=True)
    account_type = Column(String(50), nullable=False, default="expense")  # expense, asset, liability, equity, income
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship("Tenant", back_populates="chart_of_accounts")


class TaxRate(Base):
    __tablename__ = "tax_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zoho_tax_id = Column(String(100), nullable=False, index=True)
    tax_name = Column(String(255), nullable=False)
    tax_percentage = Column(Float, nullable=False, default=0.0)
    tax_type = Column(String(50), nullable=False, default="GST")  # GST, TDS, TCS
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship("Tenant", back_populates="tax_rates")


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zoho_contact_id = Column(String(100), nullable=True, index=True)
    vendor_name = Column(String(255), nullable=False)
    gstin = Column(String(15), nullable=True, index=True)
    pan = Column(String(10), nullable=True, index=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    approval_status = Column(String(50), nullable=False, default="APPROVED")  # APPROVED, PENDING, REJECTED
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tenant = relationship("Tenant", back_populates="vendors")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), nullable=False, default="default-tenant-001", index=True)
    file_path = Column(String(512), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    
    # Status State Machine
    status = Column(String(50), nullable=False, default="PENDING", index=True)
    accounting_status = Column(String(50), nullable=True, default=None)
    approval_status = Column(String(50), nullable=False, default="PENDING_REVIEW")  # PENDING_REVIEW, APPROVED, REJECTED
    export_status = Column(String(50), nullable=False, default="NOT_EXPORTED")  # NOT_EXPORTED, EXPORTING, EXPORTED, FAILED
    
    # External / Zoho References
    invoice_type = Column(String(50), nullable=False, default="VENDOR_INVOICE")
    zoho_bill_id = Column(String(100), nullable=True, index=True)
    zoho_bill_number = Column(String(100), nullable=True)
    exported_at = Column(DateTime(timezone=True), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)

    # Errors & Metrics
    error_message = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    accounting_confidence = Column(Float, nullable=True)
    
    # Dual-State JSONB Outputs
    raw_vlm_output = Column(JSONB, nullable=True)
    current_vlm_output = Column(JSONB, nullable=True)
    accounting_output = Column(JSONB, nullable=True)
    current_accounting_output = Column(JSONB, nullable=True)

    # Stage 4-6 Deterministic Engine Outputs
    gst_result = Column(JSONB, nullable=True)
    itc_result = Column(JSONB, nullable=True)
    financial_validation_result = Column(JSONB, nullable=True)
    journal_entry = Column(JSONB, nullable=True)
    
    # Email Ingestion Metadata
    email_subject = Column(String(255), nullable=True)
    email_sender = Column(String(255), nullable=True)
    email_received_at = Column(DateTime(timezone=True), nullable=True)
    email_message_id = Column(String(255), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    journal_entry_rel = relationship("JournalEntry", back_populates="invoice", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, file_name={self.file_name}, status={self.status}, export_status={self.export_status})>"


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(String(50), primary_key=True, default="imap_email")
    status = Column(String(50), nullable=False, default="disconnected")
    config = Column(JSONB, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Integration(id={self.id}, status={self.status})>"


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    tenant_id = Column(String(64), nullable=False, default="default-tenant-001", index=True)
    entry_date = Column(String(50), nullable=True)
    total_debit = Column(Float, nullable=False, default=0.0)
    total_credit = Column(Float, nullable=False, default=0.0)
    difference = Column(Float, nullable=False, default=0.0)
    balanced = Column(Boolean, nullable=False, default=True)
    is_balanced = Column(Boolean, nullable=False, default=True)
    status = Column(String(50), nullable=False, default="BALANCED", index=True)  # BALANCED, UNBALANCED, REVIEW_REQUIRED, DRAFT, POSTED
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    invoice = relationship("Invoice", back_populates="journal_entry_rel")
    lines = relationship("JournalLineModel", back_populates="journal_entry", cascade="all, delete-orphan", order_by="JournalLineModel.line_number")

    def __repr__(self) -> str:
        return f"<JournalEntry(id={self.id}, invoice_id={self.invoice_id}, status={self.status}, balanced={self.balanced})>"


class JournalLineModel(Base):
    __tablename__ = "journal_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journal_entry_id = Column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_number = Column(Integer, nullable=True, default=1)
    account_id = Column(String(100), nullable=True)
    account_name = Column(String(255), nullable=False)
    line_type = Column(String(50), nullable=False)  # EXPENSE, INPUT_TAX, TDS_PAYABLE, ACCOUNTS_PAYABLE, ROUND_OFF, DR, CR
    debit = Column(Float, nullable=False, default=0.0)
    credit = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
    source_line_index = Column(Integer, nullable=True)
    provenance = Column(String(50), nullable=False, default="DETERMINISTIC")
    description = Column(Text, nullable=True)
    cost_center = Column(String(100), nullable=True)
    project = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    journal_entry = relationship("JournalEntry", back_populates="lines")

    def __repr__(self) -> str:
        return f"<JournalLineModel(id={self.id}, account_id={self.account_id}, debit={self.debit}, credit={self.credit})>"


# Alias for backward compatibility
JournalLine = JournalLineModel


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), nullable=False, default="default-tenant-001", index=True)
    invoice_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)  # UPLOAD, EDIT_FIELD, OVERRIDE_ACCOUNT, APPROVE, REJECT, EXPORT_ZOHO
    field_name = Column(String(100), nullable=True)
    before_value = Column(Text, nullable=True)
    after_value = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
