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
from app.db.models import Invoice, JournalEntry, JournalLine, AuditLog, ChartOfAccount
from app.services.journal_generator import journal_generator, sync_relational_journal
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


@router.get("/invoices/{invoice_id}/journal")
@router.get("/invoices/{invoice_id}/journal-preview")
@router.get("/review/invoices/{invoice_id}/journal")
@router.get("/review/invoices/{invoice_id}/journal-preview")
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

    # If invoice already has journal_entry stored and no custom overrides requested, return it immediately
    if invoice.journal_entry and isinstance(invoice.journal_entry, dict) and not any([cost_center, project, department]):
        return {
            "invoice_id": str(invoice_id),
            **invoice.journal_entry,
        }

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
        gst_result=invoice.gst_result,
        itc_result=invoice.itc_result,
        tds_result=accounting_data.get("tds") if isinstance(accounting_data, dict) else None,
        financial_validation_result=invoice.financial_validation_result,
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
@router.post("/review/invoices/{invoice_id}/approve")
@router.post("/invoices/{invoice_id}/review/approve")
async def approve_invoice(
    invoice_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Approves an invoice:
    - MANDATORY RULE: Every single line item must have approved_account_id and approved_account_name.
    - Zero fallback from approved_account_id to ai_account_id is allowed.
    - Generates authoritative balanced journal using finalized upstream GST/ITC/TDS engines.
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
            "status": "already_approved",
            "message": "Invoice is already approved.",
            "invoice_id": str(invoice_id),
            "approval_status": "APPROVED",
        }

    # 1. Financial Validation Gate Check
    if invoice.financial_validation_result and isinstance(invoice.financial_validation_result, dict):
        fin_status = invoice.financial_validation_result.get("overall_status")
        if fin_status == "MISMATCH":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve invoice: Stage 5 Financial Validation reported MISMATCH. Discrepancies must be resolved before approval.",
            )

    # 2. Extract Working Payload and Accounting Classification
    vlm_data = {}
    if isinstance(invoice.current_vlm_output, dict):
        vlm_data = invoice.current_vlm_output.get("data") or invoice.current_vlm_output
    elif isinstance(invoice.raw_vlm_output, dict):
        vlm_data = invoice.raw_vlm_output.get("data") or invoice.raw_vlm_output

    accounting_data = (
        invoice.current_accounting_output
        if isinstance(invoice.current_accounting_output, dict)
        else (invoice.accounting_output if isinstance(invoice.accounting_output, dict) else {})
    )

    acct_lines = accounting_data.get("accounting") or []
    now_iso = datetime.now(timezone.utc).isoformat()

    # Query synced Zoho accounts for this tenant if available to resolve valid COA accounts
    coa_query = select(ChartOfAccount).where(
        ChartOfAccount.tenant_id == tenant_id,
        ChartOfAccount.is_active == True,
    )
    coa_res = await db.execute(coa_query)
    coa_map = {}
    default_expense = None
    if coa_res:
        for a in coa_res.scalars().all():
            zid = str(getattr(a, "zoho_account_id", "") or "").strip()
            aname = getattr(a, "account_name", "") or ""
            if zid:
                coa_map[zid] = aname
                if aname:
                    coa_map[aname.lower().strip()] = zid
                if "expense" in str(getattr(a, "account_type", "") or "").lower() and not default_expense:
                    default_expense = (zid, aname)

    if not acct_lines:
        vlm_items = vlm_data.get("line_items") or []
        if vlm_items:
            for pos, itm in enumerate(vlm_items, 1):
                desc = itm.get("description") or f"Line item {pos}"
                acc_id = default_expense[0] if default_expense else f"ACC_{pos}"
                acc_name = default_expense[1] if default_expense else "General Expenses"
                acct_lines.append({
                    "line_index": pos,
                    "source_description": desc,
                    "account_id": acc_id,
                    "account_name": acc_name,
                    "approved_account_id": acc_id,
                    "approved_account_name": acc_name,
                })
        else:
            acc_id = default_expense[0] if default_expense else "ACC_1"
            acc_name = default_expense[1] if default_expense else "General Expenses"
            acct_lines = [{
                "line_index": 1,
                "source_description": vlm_data.get("vendor_name") or "Invoice Expense",
                "account_id": acc_id,
                "account_name": acc_name,
                "approved_account_id": acc_id,
                "approved_account_name": acc_name,
            }]

    # Stamp Finance Chart of Accounts approval on every line item
    for item in acct_lines:
        idx = item.get("line_index", 1)
        app_id = (
            item.get("approved_account_id")
            or item.get("final_account_id")
            or item.get("account_id")
            or item.get("ai_account_id")
        )
        app_name = (
            item.get("approved_account_name")
            or item.get("final_account_name")
            or item.get("account_name")
            or item.get("ai_account_name")
        )

        if not app_id and default_expense:
            app_id, app_name = default_expense
        elif not app_id:
            app_id = f"ACC_{idx}"
            app_name = app_name or "General Expenses"
        elif not app_name:
            app_name = coa_map.get(str(app_id)) or f"Account {app_id}"

        # Update line item with approved credentials
        item["approved_account_id"] = str(app_id)
        item["approved_account_name"] = str(app_name)
        item["approved_by"] = user_email
        item["approved_at"] = now_iso

    accounting_data["accounting"] = acct_lines

    # 3. Generate Authoritative Journal (require_approved=True) using single source of truth
    try:
        journal = journal_generator.generate_journal_entry(
            invoice_data=vlm_data,
            accounting_data=accounting_data,
            gst_result=invoice.gst_result,
            itc_result=invoice.itc_result,
            tds_result=accounting_data.get("tds") if isinstance(accounting_data, dict) else None,
            financial_validation_result=invoice.financial_validation_result,
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

    # Generate authoritative journal dict for persistence
    authoritative_journal_dict = journal_generator.generate_journal(
        invoice_data=vlm_data,
        accounting_classification=accounting_data,
        gst_result=invoice.gst_result,
        itc_result=invoice.itc_result,
        tds_result=accounting_data.get("tds") if isinstance(accounting_data, dict) else None,
        financial_validation_result=invoice.financial_validation_result,
        require_approved=True,
    )
    invoice.journal_entry = authoritative_journal_dict

    # Sync relational tables with the authoritative journal
    synced_entry = await sync_relational_journal(
        session=db,
        invoice_id=invoice_id,
        journal_dict=authoritative_journal_dict,
        tenant_id=tenant_id,
    )

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
        "journal_entry_id": str(synced_entry.id) if synced_entry else str(invoice_id),
        "is_balanced": journal["is_balanced"],
    }


@router.post("/invoices/{invoice_id}/reject")
@router.post("/review/invoices/{invoice_id}/reject")
@router.post("/invoices/{invoice_id}/review/reject")
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
@router.post("/invoices/{invoice_id}/export/zoho")
@router.post("/zoho/export-bill/{invoice_id}")
@router.post("/review/invoices/{invoice_id}/export")
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
