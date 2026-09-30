import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Numeric,
    Text,
    DateTime,
    Date,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(64), primary_key=True)  # e.g. "default-tenant-001"
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    books_closed_through_date = Column(Date, nullable=True, default=None)
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
    zoho_connections = relationship("ZohoConnection", back_populates="tenant", cascade="all, delete-orphan")
    chart_of_accounts = relationship("ChartOfAccount", back_populates="tenant", cascade="all, delete-orphan")
    tax_rates = relationship("TaxRate", back_populates="tenant", cascade="all, delete-orphan")
    vendors = relationship("Vendor", back_populates="tenant", cascade="all, delete-orphan")
    invitations = relationship("UserInvitation", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=True)
    hashed_password = synonym("password_hash")
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default="FINANCE")  # ADMIN, FINANCE_ADMIN, FINANCE, FINANCE_USER, FINANCE_MANAGER, FINANCE_REVIEWER, DATA_REVIEWER, VIEWER, CUSTOMER
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
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
    zoho_connections = relationship("ZohoConnection", back_populates="user", cascade="all, delete-orphan")


class UserInvitation(Base):
    __tablename__ = "user_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email = Column(String(255), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="FINANCE_USER")
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, ACCEPTED, EXPIRED, REVOKED, OTP_VERIFICATION_PENDING, EMAIL_VERIFIED, LOCKED
    email_delivery_status = Column(String(50), nullable=True, default="PENDING")  # EMAIL_DELIVERY_ACCEPTED, DELIVERY_FAILED
    otp_hash = Column(String(255), nullable=True)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    otp_attempts = Column(Integer, nullable=False, default=0)
    otp_last_sent_at = Column(DateTime(timezone=True), nullable=True)
    otp_verified_at = Column(DateTime(timezone=True), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
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

    tenant = relationship("Tenant", back_populates="invitations")
    inviter = relationship("User", foreign_keys=[invited_by])


class ZohoConnection(Base):
    __tablename__ = "zoho_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_zoho_tenant_user"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
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

    tenant = relationship("Tenant", back_populates="zoho_connections")
    user = relationship("User", back_populates="zoho_connections")


# Alias for backward compatibility
ZohoCredential = ZohoConnection


class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(String(100), nullable=True, index=True)
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
    organization_id = Column(String(100), nullable=True, index=True)
    zoho_tax_id = Column(String(100), nullable=False, index=True)
    tax_name = Column(String(255), nullable=False)
    tax_percentage = Column(Float, nullable=False, default=0.0)
    tax_type = Column(String(50), nullable=False, default="GST")  # GST, TDS, TCS
    tax_section = Column(String(100), nullable=True)  # Statutory/Zoho section slug, e.g. professional_fees, technical_services
    tax_description = Column(String(255), nullable=True)
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


class VendorYTDCache(Base):
    """
    Cache for vendor-level pre-tax Financial Year YTD amounts retrieved from Zoho Books.
    Note: Zoho Books remains the authoritative source of truth.
    This table caches calculated YTD subtotals scoped by tenant, active Zoho organization,
    vendor contact ID, and Indian Financial Year.
    """
    __tablename__ = "vendor_ytd_cache"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "organization_id",
            "zoho_contact_id",
            "financial_year_start",
            name="uq_vendor_ytd_fy",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(String(100), nullable=False, index=True)
    zoho_contact_id = Column(String(100), nullable=False, index=True)
    financial_year_start = Column(Date, nullable=False, index=True)  # e.g. 2026-04-01
    financial_year_end = Column(Date, nullable=False)                # e.g. 2027-03-31
    ytd_pretax_amount = Column(Numeric(15, 2), nullable=False, default=Decimal("0.00"))
    calculated_at = Column(DateTime(timezone=True), nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=False)
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


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(String(100), nullable=True, index=True)
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
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_user_id = synonym("user_id")
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

    # Closed Accounting Period & Posting Date Controls
    posting_date = Column(Date, nullable=True, default=None, index=True)
    period_resolution = Column(String(50), nullable=False, default="NONE", index=True)
    period_resolution_reason = Column(Text, nullable=True)
    period_resolved_by = Column(String(255), nullable=True)
    period_resolved_at = Column(DateTime(timezone=True), nullable=True)
    # Accounting Period & Previous-FY Decision
    period_category = Column(String(50), nullable=True)  # CURRENT_MONTH, PREVIOUS_MONTH_CURRENT_FY, PREVIOUS_FINANCIAL_YEAR, CURRENT_FINANCIAL_YEAR, FUTURE_PERIOD
    period_decision = Column(String(50), nullable=False, default="NOT_REQUIRED")  # NOT_REQUIRED, PENDING, CONTINUE, CANCELLED

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

    # Invoice Classification & Origin Fields
    financial_relevance = Column(String(50), nullable=True, index=True)
    document_type = Column(String(50), nullable=True, index=True)
    invoice_origin = Column(String(50), nullable=True, default="INDIAN", index=True)  # INDIAN, FOREIGN_SERVICE, REVIEW_REQUIRED, UNSUPPORTED_FOREIGN_GOODS
    currency = Column(String(10), nullable=True, default="INR")
    classification_confidence = Column(Float, nullable=True)
    classification_reason = Column(Text, nullable=True)
    classification_model = Column(String(100), nullable=True)
    classification_source = Column(String(50), nullable=True, default="SYSTEM")
    classification_override = Column(String(50), nullable=True)
    classification_override_reason = Column(Text, nullable=True)
    classified_by = Column(String(100), nullable=True)
    classified_at = Column(DateTime(timezone=True), nullable=True)

    # Foreign Currency & FX Fields (Step 1 Foundation)
    original_currency = Column(String(10), nullable=True, default="INR")
    original_total_amount = Column(Numeric(15, 2), nullable=True)
    original_taxable_amount = Column(Numeric(15, 2), nullable=True)
    exchange_rate = Column(Numeric(15, 6), nullable=True, default=Decimal("1.000000"))
    exchange_rate_date = Column(Date, nullable=True)
    exchange_rate_source = Column(String(100), nullable=True, default="SYSTEM_DEFAULT")
    converted_total_inr = Column(Numeric(15, 2), nullable=True)
    converted_taxable_inr = Column(Numeric(15, 2), nullable=True)
    fx_rate_overridden = Column(Boolean, nullable=False, default=False)
    fx_override_reason = Column(Text, nullable=True)
    fx_original_rate = Column(Numeric(15, 6), nullable=True)

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
    owner = relationship("User", foreign_keys=[user_id], backref="owned_invoices")

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, file_name={self.file_name}, status={self.status}, export_status={self.export_status})>"


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(String(255), primary_key=True, default="imap_email")
    tenant_id = Column(
        String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, default="default-tenant-001", index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
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

    user = relationship("User", backref="integrations")


class EmailConnection(Base):
    __tablename__ = "email_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True, index=True)
    user_id_str = Column(String(100), nullable=True, unique=True, index=True)
    email_address = Column(String(255), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    imap_host = Column(String(255), nullable=False, default="imap.gmail.com")
    imap_port = Column(Integer, nullable=False, default=993)
    is_active = Column(Boolean, nullable=False, default=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    # Incremental polling state — user-specific, independent per user
    # NULL = user has never completed a successful poll (first poll pending)
    last_successful_poll_at = Column(DateTime(timezone=True), nullable=True)
    # Set to TRUE only after the first successful manual poll completes
    automatic_polling_enabled = Column(Boolean, nullable=False, default=False)
    # Lightweight mutex: prevents two concurrent polls for the same connection
    is_polling = Column(Boolean, nullable=False, default=False)

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

class HitlReview(Base):
    __tablename__ = "hitl_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    stage = Column(String(50), nullable=False)  # EXTRACTION, FINAL_FINANCE
    reviewer_id = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="APPROVED")  # APPROVED, REJECTED
    
    input_snapshot = Column(JSONB, nullable=True)
    corrected_output = Column(JSONB, nullable=True)
    changes = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime(timezone=True), nullable=True, default=lambda: datetime.now(timezone.utc))

