import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Logs immutable audit events for compliance, approvals, and field-level modifications."""

    @staticmethod
    async def log_event(
        db: AsyncSession,
        tenant_id: str,
        action: str,
        invoice_id: Optional[UUID] = None,
        user_email: Optional[str] = "finance@sakshi.ai",
        field_name: Optional[str] = None,
        before_value: Optional[str] = None,
        after_value: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AuditLog:
        log_entry = AuditLog(
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            user_email=user_email,
            action=action,
            field_name=field_name,
            before_value=str(before_value) if before_value is not None else None,
            after_value=str(after_value) if after_value is not None else None,
            reason=reason,
        )
        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)
        logger.info(f"[AUDIT] Tenant={tenant_id} Invoice={invoice_id} Action={action} Field={field_name}")
        return log_entry


audit_service = AuditService()
