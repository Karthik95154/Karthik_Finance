import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.db.models import Invoice, HitlReview
from app.core.security import AuthenticatedUser, get_current_user, require_roles
from app.services.invoice_processing import process_accounting_downstream_background
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Schemas
# ============================================================================

class ExtractionApproveRequest(BaseModel):
    corrected_data: Dict[str, Any]

    @validator("corrected_data")
    def validate_math(cls, v):
        total_amount = v.get("total_amount")
        subtotal = v.get("subtotal") or 0.0
        tax_total = v.get("tax_total") or 0.0
        
        # We can add more strict math checks here if needed
        # e.g. assert abs(subtotal + tax_total - total_amount) < 1.0
        return v

class FinalApproveRequest(BaseModel):
    # Could include final corrected outputs if we allow edits in final hitl
    final_accounting: Dict[str, Any] = {}
    final_journal: Dict[str, Any] = {}

# ============================================================================
# Endpoints
# ============================================================================

@router.get("/invoices/{invoice_id}/hitl/extraction")
async def get_extraction_hitl(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(["ADMIN", "DATA_REVIEWER"])),
):
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return {
        "id": invoice.id,
        "file_name": invoice.file_name,
        "file_path": invoice.file_path,
        "mime_type": invoice.mime_type or "application/pdf",
        "status": invoice.status,
        "raw_vlm_output": invoice.raw_vlm_output,
        "current_vlm_output": invoice.current_vlm_output or invoice.raw_vlm_output,
    }

@router.post("/invoices/{invoice_id}/hitl/extraction/approve")
async def approve_extraction_hitl(
    invoice_id: uuid.UUID,
    payload: ExtractionApproveRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(["ADMIN", "DATA_REVIEWER"])),
):
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != "HITL_REVIEW":
        raise HTTPException(status_code=409, detail=f"Invoice is not in HITL_REVIEW state (current: {invoice.status})")

    # Create HitlReview Audit record
    hitl_review = HitlReview(
        invoice_id=invoice.id,
        stage="EXTRACTION",
        reviewer_id=user.id,
        status="APPROVED",
        input_snapshot=invoice.raw_vlm_output,
        corrected_output=payload.corrected_data,
        changes={"msg": "Saved via HITL Extraction Review"}, # Would diff structurally if requested
        approved_at=datetime.now(timezone.utc)
    )
    db.add(hitl_review)

    # Update Invoice
    invoice.current_vlm_output = payload.corrected_data
    invoice.status = "ACCOUNTING_PROCESSING"
    await db.commit()

    # Trigger downstream asynchronously
    asyncio.create_task(process_accounting_downstream_background(invoice.id))

    return {"message": "Extraction approved. Processing downstream."}


@router.get("/invoices/{invoice_id}/hitl/final")
async def get_final_hitl(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE_REVIEWER", "FINANCE", "DATA_REVIEWER"])),
):
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return {
        "id": invoice.id,
        "file_name": invoice.file_name,
        "file_path": invoice.file_path,
        "mime_type": invoice.mime_type or "application/pdf",
        "status": invoice.status,
        "approval_status": invoice.approval_status,
        "accounting_status": invoice.accounting_status,
        "raw_vlm_output": invoice.raw_vlm_output,
        "current_vlm_output": invoice.current_vlm_output or invoice.raw_vlm_output,
        "accounting_output": invoice.accounting_output,
        "current_accounting_output": invoice.current_accounting_output or invoice.accounting_output,
        "gst_result": invoice.gst_result,
        "itc_result": invoice.itc_result,
        "financial_validation_result": invoice.financial_validation_result,
        "journal_entry": invoice.journal_entry,
        "created_at": invoice.created_at,
        "updated_at": invoice.updated_at,
    }


@router.post("/invoices/{invoice_id}/hitl/final/approve")
async def approve_final_hitl(
    invoice_id: uuid.UUID,
    payload: FinalApproveRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE_REVIEWER", "FINANCE"])),
):
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != "FINAL_HITL_REVIEW":
        raise HTTPException(status_code=409, detail=f"Invoice is not in FINAL_HITL_REVIEW state (current: {invoice.status})")

    # Create HitlReview Audit record
    hitl_review = HitlReview(
        invoice_id=invoice.id,
        stage="FINAL_FINANCE",
        reviewer_id=user.id,
        status="APPROVED",
        input_snapshot=invoice.accounting_output,
        corrected_output=payload.final_accounting,
        changes={"msg": "Saved via Final HITL Review"},
        approved_at=datetime.now(timezone.utc)
    )
    db.add(hitl_review)

    invoice.status = "HITL_COMPLETED"
    invoice.approval_status = "PENDING_FINANCE_APPROVAL"
    invoice.accounting_status = "COMPLETED"
    invoice.locked_at = datetime.now(timezone.utc)

    # Overwrite if edited
    if payload.final_accounting:
        invoice.current_accounting_output = payload.final_accounting
    if payload.final_journal:
        invoice.journal_entry = payload.final_journal
        from app.services.invoice_processing import sync_relational_journal
        await sync_relational_journal(db, invoice.id, payload.final_journal)

    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "HITL review completed. Invoice moved to HITL_COMPLETED and is now awaiting final Finance approval in Main App."}


@router.get("/invoices/{invoice_id}/hitl/history")
async def get_invoice_hitl_history(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(["ADMIN", "DATA_REVIEWER", "FINANCE_REVIEWER", "FINANCE"])),
):
    """
    Returns the complete chronological HITL review and approval history for an invoice.
    """
    query = (
        select(HitlReview)
        .where(HitlReview.invoice_id == invoice_id)
        .order_by(HitlReview.created_at.desc())
    )
    result = await db.execute(query)
    reviews = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "invoice_id": str(r.invoice_id),
            "stage": r.stage,
            "reviewer_id": r.reviewer_id,
            "status": r.status,
            "changes": r.changes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
        }
        for r in reviews
    ]


@router.get("/hitl/history")
async def get_all_hitl_history(
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(["ADMIN", "DATA_REVIEWER", "FINANCE_REVIEWER", "FINANCE"])),
):
    """
    Returns all invoices that have undergone HITL review along with their audit history.
    """
    from sqlalchemy.orm import selectinload

    query = (
        select(Invoice)
        .where(Invoice.tenant_id == user.tenant_id)
        .order_by(Invoice.updated_at.desc())
    )
    result = await db.execute(query)
    all_invoices = result.scalars().all()

    # Filter invoices that reached HITL_COMPLETED or have review records
    history_invoices = []
    for inv in all_invoices:
        vlm_data = inv.current_vlm_output.get("data") if isinstance(inv.current_vlm_output, dict) and isinstance(inv.current_vlm_output.get("data"), dict) else (inv.raw_vlm_output.get("data") if isinstance(inv.raw_vlm_output, dict) and isinstance(inv.raw_vlm_output.get("data"), dict) else {})
        
        # Get hitl reviews
        r_query = select(HitlReview).where(HitlReview.invoice_id == inv.id).order_by(HitlReview.created_at.desc())
        r_res = await db.execute(r_query)
        reviews = r_res.scalars().all()

        if reviews or inv.status in ("HITL_COMPLETED", "COMPLETED", "EXPORTED"):
            history_invoices.append({
                "id": str(inv.id),
                "file_name": inv.file_name,
                "status": inv.status,
                "approval_status": inv.approval_status,
                "accounting_status": inv.accounting_status,
                "vendor_name": vlm_data.get("vendor_name") or inv.file_name,
                "invoice_number": vlm_data.get("invoice_number"),
                "total_amount": vlm_data.get("total_amount"),
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
                "reviews": [
                    {
                        "id": str(r.id),
                        "stage": r.stage,
                        "reviewer_id": r.reviewer_id,
                        "status": r.status,
                        "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                    }
                    for r in reviews
                ]
            })

    return history_invoices
