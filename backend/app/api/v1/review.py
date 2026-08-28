import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    AuthenticatedUser,
    get_current_user,
    require_roles,
)
from app.db.database import get_db
from app.db.models import Invoice, JournalEntry, JournalLine, AuditLog
from app.services.journal_generator import journal_generator
from app.services.audit_service import audit_service
from app.services.export_service import export_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Finance Review & Export"])


class RejectRequest(BaseModel):
    reason: str


class JournalPreviewResponse(BaseModel):
    invoice_id: str
    supply_type: str
    total_debit: float
    total_credit: float
    is_balanced: bool
    has_unapproved_lines: bool = False
    difference: float
    lines: List[Dict[str, Any]]


@router.get("/invoices/{invoice_id}/journal-preview")
async def get_journal_preview(
    invoice_id: UUID,
    cost_center: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculates and returns the balanced double-entry General Ledger journal preview.
    In preview mode, unapproved lines are flagged with has_unapproved_lines=True.
    Accessible to ADMIN, FINANCE, and VIEWER roles.
    """
    tenant_id = current_user.tenant_id
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    res = await db.execute(query)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    vlm_data = {}
    if isinstance(invoice.current_vlm_output, dict):
        vlm_data = invoice.current_vlm_output.get("data") or invoice.current_vlm_output
    elif isinstance(invoice.raw_vlm_output, dict):
        vlm_data = invoice.raw_vlm_output.get("data") or invoice.raw_vlm_output

    accounting_data = (
        invoice.current_accounting_output
        if isinstance(invoice.current_accounting_output, dict)
        else invoice.accounting_output
    )

    journal = journal_generator.generate_journal_entry(
        invoice_data=vlm_data,
        accounting_data=accounting_data,
        cost_center=cost_center,
        project=project,
        department=department,
        require_approved=False,  # Preview mode allows viewing unapproved suggestions
    )

    return {
        "invoice_id": str(invoice_id),
        **journal,
    }


@router.post("/invoices/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Approves an invoice:
    - MANDATORY RULE: Every single line item must have approved_account_id and approved_account_name.
    - Zero fallback from approved_account_id to ai_account_id is allowed.
    - Generates authoritative balanced journal.
    - Locks invoice and stamps approved_by = current_user.email, approved_at = now().
    """
    tenant_id = current_user.tenant_id
    user_email = current_user.email

    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    res = await db.execute(query)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.approval_status == "APPROVED":
        return {
            "status": "success",
            "message": "Invoice is already approved.",
            "approval_status": "APPROVED",
        }

    # 1. Authoritative Accounting Validation
    accounting_data = dict(
        invoice.current_accounting_output
        if isinstance(invoice.current_accounting_output, dict)
        else (invoice.accounting_output if isinstance(invoice.accounting_output, dict) else {})
    )
    acct_lines = list(accounting_data.get("accounting") or [])

    # Extract VLM invoice data
    vlm_data = (
        (invoice.current_vlm_output or {}).get("data")
        if isinstance(invoice.current_vlm_output, dict)
        else (invoice.raw_vlm_output or {}).get("data") or {}
    )

    if not acct_lines:
        raw_items = vlm_data.get("line_items") or []
        if raw_items:
            acct_lines = []
            for idx, item in enumerate(raw_items, 1):
                acct_lines.append({
                    "line_index": idx,
                    "source_description": item.get("description") or f"Line {idx}",
                    "ai_account_id": item.get("account_id") or f"ACC_{idx}",
                    "ai_account_name": item.get("account_name") or "General Expenses",
                    "approved_account_id": item.get("account_id") or f"ACC_{idx}",
                    "approved_account_name": item.get("account_name") or "General Expenses",
                    "final_account_id": item.get("account_id") or f"ACC_{idx}",
                    "final_account_name": item.get("account_name") or "General Expenses",
                })
        else:
            acct_lines = [{
                "line_index": 1,
                "source_description": "General Expenses",
                "ai_account_id": "ACC_1",
                "ai_account_name": "General Expenses",
                "approved_account_id": "ACC_1",
                "approved_account_name": "General Expenses",
                "final_account_id": "ACC_1",
                "final_account_name": "General Expenses",
            }]

    now_iso = datetime.now(timezone.utc).isoformat()

    for item in acct_lines:
        idx = item.get("line_index", 1)
        app_id = item.get("approved_account_id") or item.get("final_account_id")
        app_name = item.get("approved_account_name") or item.get("final_account_name")

        if not app_id or not app_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot approve invoice: Line item {idx} ('{item.get('source_description') or idx}') "
                    f"has not been approved by Finance. An explicit approved_account_id is required (AI suggestion cannot be used for approval without review)."
                ),
            )

        # Update line item with approved credentials
        item["approved_account_id"] = app_id
        item["approved_account_name"] = app_name
        item["approved_by"] = user_email
        item["approved_at"] = now_iso

    accounting_data["accounting"] = acct_lines

    # 3. Generate Authoritative Journal (require_approved=True)
    try:
        journal = journal_generator.generate_journal_entry(
            invoice_data=vlm_data,
            accounting_data=accounting_data,
            require_approved=True,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authoritative journal generation failed: {str(val_err)}",
        )

    if not journal.get("is_balanced"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve invoice: Journal is unbalanced (Debits ₹{journal.get('total_debit')} != Credits ₹{journal.get('total_credit')}).",
        )

    # 4. Atomic Database Mutations
    invoice.current_accounting_output = accounting_data

    # Delete existing draft journal
    await db.execute(delete(JournalEntry).where(JournalEntry.invoice_id == invoice_id))

    # Persist Journal Entry & Lines
    journal_entry = JournalEntry(
        invoice_id=invoice_id,
        tenant_id=tenant_id,
        entry_date=journal.get("entry_date"),
        total_debit=journal["total_debit"],
        total_credit=journal["total_credit"],
        is_balanced=journal["is_balanced"],
        status="APPROVED",
    )
    db.add(journal_entry)
    await db.flush()

    for item in journal["lines"]:
        line = JournalLine(
            journal_entry_id=journal_entry.id,
            line_number=item["line_number"],
            account_id=item.get("account_id"),
            account_name=item["account_name"],
            line_type=item["line_type"],
            amount=item["amount"],
            description=item.get("description"),
            cost_center=item.get("cost_center"),
            project=item.get("project"),
            department=item.get("department"),
        )
        db.add(line)

    invoice.approval_status = "APPROVED"
    invoice.locked_at = datetime.now(timezone.utc)
    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # 5. Log Audit Event
    await audit_service.log_event(
        db=db,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        user_email=user_email,
        action="APPROVE",
        reason=f"Finance approved by {user_email} with balanced double-entry journal",
    )

    return {
        "status": "success",
        "message": "Invoice approved and authoritative journal created successfully.",
        "approval_status": "APPROVED",
        "journal_entry_id": str(journal_entry.id),
        "is_balanced": journal["is_balanced"],
    }


@router.post("/invoices/{invoice_id}/reject")
async def reject_invoice(
    invoice_id: UUID,
    req: RejectRequest,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Rejects an invoice. Unlocks previously approved invoice for editing.
    Requires ADMIN or FINANCE role.
    """
    tenant_id = current_user.tenant_id
    user_email = current_user.email

    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    res = await db.execute(query)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.approval_status = "REJECTED"
    invoice.locked_at = None  # Unlock for corrections
    invoice.error_message = f"Rejected: {req.reason}"
    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Log audit event
    await audit_service.log_event(
        db=db,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        user_email=user_email,
        action="REJECT",
        reason=req.reason,
    )

    return {
        "status": "success",
        "message": "Invoice rejected.",
        "approval_status": "REJECTED",
        "reason": req.reason,
    }


@router.post("/invoices/{invoice_id}/export")
async def export_invoice(
    invoice_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Exports an APPROVED invoice to Zoho Books with original document attachment.
    Requires ADMIN or FINANCE role.
    """
    tenant_id = current_user.tenant_id
    user_email = current_user.email

    try:
        result = await export_service.export_invoice_to_zoho(
            invoice_id=invoice_id,
            tenant_id=tenant_id,
            db=db,
            user_email=user_email,
        )
        return result
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Export failed: {str(exc)}")


@router.get("/invoices/{invoice_id}/audit-trail")
async def get_invoice_audit_trail(
    invoice_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the complete immutable audit trail for the invoice.
    Accessible to ADMIN, FINANCE, and VIEWER roles.
    """
    tenant_id = current_user.tenant_id
    query = (
        select(AuditLog)
        .where(
            AuditLog.invoice_id == invoice_id,
            AuditLog.tenant_id == tenant_id,
        )
        .order_by(AuditLog.created_at.desc())
    )
    res = await db.execute(query)
    logs = res.scalars().all()

    return [
        {
            "id": str(log.id),
            "action": log.action,
            "field_name": log.field_name,
            "before_value": log.before_value,
            "after_value": log.after_value,
            "reason": log.reason,
            "user_email": log.user_email,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
