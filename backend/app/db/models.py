import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
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
