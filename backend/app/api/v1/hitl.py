import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.db.models import Invoice, HitlReview, Tenant, AuditLog
from app.core.security import AuthenticatedUser, get_current_user, require_roles
from app.services.invoice_processing import process_accounting_downstream_background, get_effective_invoice_data
from app.core.date_utils import check_accounting_period, parse_and_normalize_date, is_date_in_closed_period
from app.services.audit_service import audit_service
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Schemas
# ============================================================================

class ExtractionApproveRequest(BaseModel):
    corrected_data: Dict[str, Any]
    posting_date: Optional[str] = None
    period_resolution: Optional[str] = None
    period_resolution_reason: Optional[str] = None

    @validator("corrected_data")
    def validate_math(cls, v):
        total_amount = v.get("total_amount")
        subtotal = v.get("subtotal") or 0.0
        tax_total = v.get("tax_total") or 0.0
        return v


class PeriodResolutionRequest(BaseModel):
    decision: str  # POST_TO_OPEN_PERIOD, PRIOR_PERIOD_EXCEPTION, FLAGGED_FOR_AUDIT
    posting_date: Optional[str] = None
    reason: Optional[str] = None


class FinalApproveRequest(BaseModel):
    final_accounting: Dict[str, Any] = {}
    final_journal: Dict[str, Any] = {}
    posting_date: Optional[str] = None
    period_resolution: Optional[str] = None
    period_resolution_reason: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/invoices/{invoice_id}/hitl/extraction")
async def get_extraction_hitl(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(["ADMIN", "DATA_REVIEWER", "FINANCE", "FINANCE_REVIEWER"])),
):
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Fetch tenant closed date
    t_query = select(Tenant).where(Tenant.id == user.tenant_id)
    t_res = await db.execute(t_query)
    tenant = t_res.scalar_one_or_none()
    books_closed_date = getattr(tenant, "books_closed_through_date", None)
    books_closed_through_date = books_closed_date.isoformat() if books_closed_date else None

    eff_data = get_effective_invoice_data(invoice)
    doc_date = eff_data.get("invoice_date")
    eff_posting = invoice.posting_date.isoformat() if invoice.posting_date else doc_date

    period_info = check_accounting_period(
        document_date=doc_date,
        posting_date=eff_posting,
        books_closed_through_date=books_closed_through_date,
        period_resolution=invoice.period_resolution or "NONE",
    )

    return {
        "id": invoice.id,
        "file_name": invoice.file_name,
        "file_path": invoice.file_path,
        "mime_type": invoice.mime_type or "application/pdf",
        "status": invoice.status,
        "raw_vlm_output": invoice.raw_vlm_output,
        "current_vlm_output": invoice.current_vlm_output or invoice.raw_vlm_output,
        "posting_date": eff_posting,
        "document_date": doc_date,
        "period_resolution": invoice.period_resolution or "NONE",
        "period_resolution_reason": invoice.period_resolution_reason,
        "period_resolved_by": invoice.period_resolved_by,
        "period_resolved_at": invoice.period_resolved_at.isoformat() if invoice.period_resolved_at else None,
        "books_closed_through_date": books_closed_through_date,
        "period_info": period_info,
    }


@router.post("/invoices/{invoice_id}/hitl/extraction/approve")
async def approve_extraction_hitl(
    invoice_id: uuid.UUID,
    payload: ExtractionApproveRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(["ADMIN", "DATA_REVIEWER", "FINANCE", "FINANCE_REVIEWER"])),
):
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != "HITL_REVIEW":
        raise HTTPException(status_code=409, detail=f"Invoice is not in HITL_REVIEW state (current: {invoice.status})")

    # Fetch tenant lock date
    t_query = select(Tenant).where(Tenant.id == user.tenant_id)
    t_res = await db.execute(t_query)
    tenant = t_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant organization '{user.tenant_id}' could not be loaded for closed period validation."
        )
    lock_date = tenant.books_closed_through_date

    # Determine document date and posting date
    doc_date = parse_and_normalize_date(payload.corrected_data.get("invoice_date"))
    if not doc_date:
        eff = get_effective_invoice_data(invoice)
        doc_date = parse_and_normalize_date(eff.get("invoice_date"))

    res_decision = (payload.period_resolution or invoice.period_resolution or "NONE").upper()
    req_posting_str = payload.posting_date or (payload.corrected_data.get("posting_date") if isinstance(payload.corrected_data, dict) else None)
    req_posting = parse_and_normalize_date(req_posting_str) or (invoice.posting_date.isoformat() if invoice.posting_date else None)

    # GATE 1 Enforcement: Closed accounting period check
    is_doc_closed = is_date_in_closed_period(doc_date, lock_date)
    if is_doc_closed:
        if res_decision == "NONE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot approve Stage 1 extraction: Invoice document date ({doc_date}) falls within a closed accounting period (Books closed through {lock_date}). An explicit period resolution must be selected before accounting can begin."
            )
        elif res_decision == "POST_TO_OPEN_PERIOD":
            if not req_posting or is_date_in_closed_period(req_posting, lock_date):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid posting date ({req_posting}): Posting date must be strictly after the books closed through date ({lock_date})."
                )
            try:
                invoice.posting_date = datetime.strptime(req_posting, "%Y-%m-%d").date()
            except ValueError:
                pass
            invoice.period_resolution = "POST_TO_OPEN_PERIOD"
            invoice.period_resolved_by = user.email
            invoice.period_resolved_at = datetime.now(timezone.utc)
        elif res_decision == "PRIOR_PERIOD_EXCEPTION":
            if user.role not in ("ADMIN", "FINANCE"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{user.role}' is not authorized to approve a Prior-Period Exception. Only FINANCE or ADMIN roles may authorize exceptions."
                )
            reason_txt = payload.period_resolution_reason or invoice.period_resolution_reason or ""
            if len(reason_txt.strip()) < 10:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Prior-Period Exception requires a detailed audit rationale (minimum 10 characters)."
                )
            target_post = req_posting or doc_date
            try:
                invoice.posting_date = datetime.strptime(target_post, "%Y-%m-%d").date() if target_post else None
            except ValueError:
                pass
            invoice.period_resolution = "PRIOR_PERIOD_EXCEPTION"
            invoice.period_resolution_reason = reason_txt.strip()
            invoice.period_resolved_by = user.email
            invoice.period_resolved_at = datetime.now(timezone.utc)

            # Log audit event for prior period exception
            await audit_service.log_event(
                db=db,
                tenant_id=user.tenant_id,
                invoice_id=invoice.id,
                user_email=user.email,
                action="PRIOR_PERIOD_EXCEPTION_APPROVED",
                field_name="posting_date",
                before_value=str(doc_date),
                after_value=str(invoice.posting_date or doc_date),
                reason=f"Prior-period exception approved by {user.role} ({user.email}). Reason: {reason_txt.strip()}",
            )
        elif res_decision == "FLAGGED_FOR_AUDIT":
            invoice.period_resolution = "FLAGGED_FOR_AUDIT"
            invoice.approval_status = "REJECTED"
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice has been flagged for audit and stopped from downstream accounting processing."
            )
    else:
        # Open period
        if req_posting:
            try:
                invoice.posting_date = datetime.strptime(req_posting, "%Y-%m-%d").date()
            except ValueError:
                pass
        elif doc_date:
            try:
                invoice.posting_date = datetime.strptime(doc_date, "%Y-%m-%d").date()
            except ValueError:
                pass
        invoice.period_resolution = "NONE"

    # Create HitlReview Audit record
    hitl_review = HitlReview(
        invoice_id=invoice.id,
        stage="EXTRACTION",
        reviewer_id=user.id,
        status="APPROVED",
        input_snapshot=invoice.raw_vlm_output,
        corrected_output=payload.corrected_data,
        changes={"msg": "Saved via HITL Extraction Review", "period_resolution": invoice.period_resolution, "posting_date": str(invoice.posting_date)},
        approved_at=datetime.now(timezone.utc)
    )
    db.add(hitl_review)

    # Update Invoice
    invoice.current_vlm_output = payload.corrected_data
    invoice.status = "ACCOUNTING_PROCESSING"
    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Trigger downstream asynchronously
    asyncio.create_task(process_accounting_downstream_background(invoice.id))

    return {
        "message": "Extraction approved. Processing downstream.",
        "posting_date": str(invoice.posting_date) if invoice.posting_date else None,
        "period_resolution": invoice.period_resolution,
    }


@router.post("/invoices/{invoice_id}/period-resolution")
async def resolve_invoice_period(
    invoice_id: uuid.UUID,
    payload: PeriodResolutionRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "DATA_REVIEWER", "FINANCE_REVIEWER"])),
):
    """
    Explicit endpoint to resolve or update the accounting period decision for an invoice.
    Enforces strict RBAC:
    - DATA_REVIEWER / FINANCE_REVIEWER can set POST_TO_OPEN_PERIOD
    - Only FINANCE / ADMIN can authorize PRIOR_PERIOD_EXCEPTION
    """
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    t_query = select(Tenant).where(Tenant.id == user.tenant_id)
    t_res = await db.execute(t_query)
    tenant = t_res.scalar_one_or_none()
    lock_date = tenant.books_closed_through_date if tenant else None

    decision = payload.decision.upper()
    eff_data = get_effective_invoice_data(invoice)
    doc_date = parse_and_normalize_date(eff_data.get("invoice_date"))

    if decision == "POST_TO_OPEN_PERIOD":
        if not payload.posting_date:
            raise HTTPException(status_code=400, detail="posting_date is required when choosing POST_TO_OPEN_PERIOD.")
        norm_post = parse_and_normalize_date(payload.posting_date)
        if not norm_post:
            raise HTTPException(status_code=400, detail="Invalid posting_date format.")
        if is_date_in_closed_period(norm_post, lock_date):
            raise HTTPException(
                status_code=400,
                detail=f"Selected posting date ({norm_post}) is within the closed period (Books closed through {lock_date}). Must be after closed date."
            )
        invoice.posting_date = datetime.strptime(norm_post, "%Y-%m-%d").date()
        invoice.period_resolution = "POST_TO_OPEN_PERIOD"
        invoice.period_resolution_reason = payload.reason
        invoice.period_resolved_by = user.email
        invoice.period_resolved_at = datetime.now(timezone.utc)

    elif decision == "PRIOR_PERIOD_EXCEPTION":
        if user.role not in ("ADMIN", "FINANCE"):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' cannot authorize prior-period exceptions. Only FINANCE or ADMIN roles permitted."
            )
        if not payload.reason or len(payload.reason.strip()) < 10:
            raise HTTPException(status_code=422, detail="Mandatory audit reason required (minimum 10 characters).")
        target_post = parse_and_normalize_date(payload.posting_date) or doc_date
        if target_post:
            invoice.posting_date = datetime.strptime(target_post, "%Y-%m-%d").date()
        invoice.period_resolution = "PRIOR_PERIOD_EXCEPTION"
        invoice.period_resolution_reason = payload.reason.strip()
        invoice.period_resolved_by = user.email
        invoice.period_resolved_at = datetime.now(timezone.utc)

        await audit_service.log_event(
            db=db,
            tenant_id=user.tenant_id,
            invoice_id=invoice.id,
            user_email=user.email,
            action="PRIOR_PERIOD_EXCEPTION_APPROVED",
            field_name="posting_date",
            before_value=str(doc_date),
            after_value=str(invoice.posting_date or doc_date),
            reason=f"Prior-period exception authorized by {user.role} ({user.email}). Rationale: {payload.reason.strip()}",
        )

    elif decision == "FLAGGED_FOR_AUDIT":
        invoice.period_resolution = "FLAGGED_FOR_AUDIT"
        invoice.period_resolution_reason = payload.reason
        invoice.period_resolved_by = user.email
        invoice.period_resolved_at = datetime.now(timezone.utc)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown decision '{payload.decision}'.")

    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "success",
        "message": f"Period resolution '{invoice.period_resolution}' applied successfully.",
        "posting_date": str(invoice.posting_date) if invoice.posting_date else None,
        "period_resolution": invoice.period_resolution,
    }


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

    # Fetch tenant lock date
    t_query = select(Tenant).where(Tenant.id == user.tenant_id)
    t_res = await db.execute(t_query)
    tenant = t_res.scalar_one_or_none()
    books_closed_date = getattr(tenant, "books_closed_through_date", None)
    books_closed_through_date = books_closed_date.isoformat() if books_closed_date else None

    eff_data = get_effective_invoice_data(invoice)
    doc_date = eff_data.get("invoice_date")
    eff_posting = invoice.posting_date.isoformat() if invoice.posting_date else doc_date

    period_info = check_accounting_period(
        document_date=doc_date,
        posting_date=eff_posting,
        books_closed_through_date=books_closed_through_date,
        period_resolution=invoice.period_resolution or "NONE",
    )

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
        "posting_date": eff_posting,
        "document_date": doc_date,
        "period_resolution": invoice.period_resolution or "NONE",
        "period_resolution_reason": invoice.period_resolution_reason,
        "period_resolved_by": invoice.period_resolved_by,
        "period_resolved_at": invoice.period_resolved_at.isoformat() if invoice.period_resolved_at else None,
        "books_closed_through_date": books_closed_through_date,
        "period_info": period_info,
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

    # Fetch tenant lock date and dynamically re-evaluate period
    t_query = select(Tenant).where(Tenant.id == user.tenant_id)
    t_res = await db.execute(t_query)
    tenant = t_res.scalar_one_or_none()
    lock_date = getattr(tenant, "books_closed_through_date", None)

    eff_data = get_effective_invoice_data(invoice)
    doc_date = parse_and_normalize_date(eff_data.get("invoice_date"))
    req_posting = parse_and_normalize_date(payload.posting_date) or (invoice.posting_date.isoformat() if invoice.posting_date else doc_date)

    if payload.period_resolution:
        invoice.period_resolution = payload.period_resolution.upper()
    if payload.period_resolution_reason:
        invoice.period_resolution_reason = payload.period_resolution_reason

    # Re-evaluate period lock
    if is_date_in_closed_period(req_posting, lock_date):
        if invoice.period_resolution != "PRIOR_PERIOD_EXCEPTION":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot approve Final HITL: Posting date ({req_posting}) falls within a closed accounting period (Books closed through {lock_date}). An authorized Prior-Period Exception is required."
            )
        elif user.role not in ("ADMIN", "FINANCE"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' cannot authorize prior-period exception."
            )

    if req_posting:
        try:
            invoice.posting_date = datetime.strptime(req_posting, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Create HitlReview Audit record
    hitl_review = HitlReview(
        invoice_id=invoice.id,
        stage="FINAL_FINANCE",
        reviewer_id=user.id,
        status="APPROVED",
        input_snapshot=invoice.accounting_output,
        corrected_output=payload.final_accounting,
        changes={"msg": "Saved via Final HITL Review", "posting_date": str(invoice.posting_date), "period_resolution": invoice.period_resolution},
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
    Returns the complete chronological HITL review and approval history for an invoice strictly scoped to the tenant.
    """
    # 1. Verify invoice exists and belongs to the authenticated user's tenant
    inv_query = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.tenant_id == user.tenant_id,
    )
    inv_res = await db.execute(inv_query)
    invoice = inv_res.scalar_one_or_none()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found.",
        )

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
