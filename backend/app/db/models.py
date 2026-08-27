import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_path = Column(String(512), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="PENDING", index=True)
    error_message = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    raw_vlm_output = Column(JSONB, nullable=True)
    current_vlm_output = Column(JSONB, nullable=True)
    accounting_output = Column(JSONB, nullable=True)
    current_accounting_output = Column(JSONB, nullable=True)
    accounting_confidence = Column(Float, nullable=True)
    accounting_status = Column(String(50), nullable=True, default=None)
    gst_result = Column(JSONB, nullable=True)
    itc_result = Column(JSONB, nullable=True)
    financial_validation_result = Column(JSONB, nullable=True)
    journal_entry = Column(JSONB, nullable=True)
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
        return f"<Invoice(id={self.id}, file_name={self.file_name}, status={self.status})>"


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    status = Column(String(50), nullable=False, default="BALANCED", index=True)
    total_debit = Column(Float, nullable=False, default=0.0)
    total_credit = Column(Float, nullable=False, default=0.0)
    difference = Column(Float, nullable=False, default=0.0)
    balanced = Column(Boolean, nullable=False, default=True)
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

    lines = relationship("JournalLineModel", back_populates="journal_entry", cascade="all, delete-orphan", order_by="JournalLineModel.created_at")

    def __repr__(self) -> str:
        return f"<JournalEntry(id={self.id}, invoice_id={self.invoice_id}, status={self.status}, balanced={self.balanced})>"


class JournalLineModel(Base):
    __tablename__ = "journal_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journal_entry_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number = Column(Integer, nullable=True)
    account_id = Column(String(100), nullable=False)
    account_name = Column(String(255), nullable=False)
    line_type = Column(String(50), nullable=False)
    debit = Column(Float, nullable=False, default=0.0)
    credit = Column(Float, nullable=False, default=0.0)
    source_line_index = Column(Integer, nullable=True)
    provenance = Column(String(50), nullable=False, default="DETERMINISTIC")
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    journal_entry = relationship("JournalEntry", back_populates="lines")

    def __repr__(self) -> str:
        return f"<JournalLineModel(id={self.id}, account_id={self.account_id}, debit={self.debit}, credit={self.credit})>"
