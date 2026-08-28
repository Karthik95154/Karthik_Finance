import logging
from typing import Any, Dict, Optional, Tuple
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Invoice

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detects duplicate invoice uploads via binary hash and business composite keys."""

    @staticmethod
    async def check_file_hash_duplicate(
        file_hash: str,
        tenant_id: str,
        db: AsyncSession,
        exclude_id: Optional[UUID] = None,
    ) -> Optional[Invoice]:
        """Checks if identical file hash already exists in tenant's records."""
        query = select(Invoice).where(
            Invoice.file_hash == file_hash,
            Invoice.tenant_id == tenant_id,
        )
        if exclude_id:
            query = query.where(Invoice.id != exclude_id)

        res = await db.execute(query)
        return res.scalar_one_or_none()

    @staticmethod
    async def check_business_duplicate(
        tenant_id: str,
        invoice_number: Optional[str],
        vendor_gstin: Optional[str],
        invoice_date: Optional[str],
        db: AsyncSession,
        exclude_id: Optional[UUID] = None,
    ) -> Optional[Invoice]:
        """Checks for business key duplicate: (tenant_id, invoice_number, vendor_gstin, invoice_date)."""
        if not invoice_number:
            return None

        query = select(Invoice).where(
            Invoice.tenant_id == tenant_id,
        )
        if exclude_id:
            query = query.where(Invoice.id != exclude_id)

        res = await db.execute(query)
        invoices = res.scalars().all()

        for inv in invoices:
            vlm_data = (
                (inv.current_vlm_output or {}).get("data")
                if isinstance(inv.current_vlm_output, dict)
                else {}
            )
            if not vlm_data and isinstance(inv.raw_vlm_output, dict):
                vlm_data = inv.raw_vlm_output.get("data") or {}

            if not vlm_data:
                continue

            existing_num = vlm_data.get("invoice_number")
            existing_gstin = vlm_data.get("vendor_gstin")
            existing_date = vlm_data.get("invoice_date")

            if existing_num and str(existing_num).strip().lower() == str(invoice_number).strip().lower():
                # If GSTIN matches or dates match
                if vendor_gstin and existing_gstin and vendor_gstin == existing_gstin:
                    return inv
                if invoice_date and existing_date and invoice_date == existing_date:
                    return inv

        return None


duplicate_detector = DuplicateDetector()
