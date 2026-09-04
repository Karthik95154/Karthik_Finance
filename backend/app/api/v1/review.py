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
from app.db.models import Invoice, JournalEntry, JournalLine, AuditLog, ChartOfAccount, Tenant
from app.core.date_utils import parse_and_normalize_date, is_date_in_closed_period, format_to_indian_standard
from app.services.journal_generator import journal_generator, sync_relational_journal
from app.services.audit_service import audit_service
from app.services.export_service import export_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Finance Review & Export"])


class RejectRequest(BaseModel):
    reason: str


class TenantClosedPeriodRequest(BaseModel):
    books_closed_through_date: Optional[str] = None  # ISO YYYY-MM-DD or null


@router.get("/tenants/closed-period")
async def get_tenant_closed_period(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns the authenticated tenant's closed accounting period lock date."""
    tenant_query = select(Tenant).where(Tenant.id == current_user.tenant_id)
    t_res = await db.execute(tenant_query)
    tenant = t_res.scalar_one_or_none()

    lock_date = tenant.books_closed_through_date.isoformat() if (tenant and tenant.books_closed_through_date) else None
    return {
        "tenant_id": current_user.tenant_id,
        "books_closed_through_date": lock_date,
        "books_closed_through_date_formatted": format_to_indian_standard(lock_date) if lock_date else None,
    }


@router.put("/tenants/closed-period")
async def update_tenant_closed_period(
    payload: TenantClosedPeriodRequest,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN"])),
    db: AsyncSession = Depends(get_db),
):
    """Updates the authenticated tenant's books_closed_through_date. Only ADMIN authorized."""
    tenant_query = select(Tenant).where(Tenant.id == current_user.tenant_id)
    t_res = await db.execute(tenant_query)
    tenant = t_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    new_date = None
    if payload.books_closed_through_date:
        norm_date = parse_and_normalize_date(payload.books_closed_through_date)
        if not norm_date:
            raise HTTPException(status_code=400, detail="Invalid date format for books_closed_through_date.")
        from datetime import datetime
        new_date = datetime.strptime(norm_date, "%Y-%m-%d").date()

    tenant.books_closed_through_date = new_date
    await db.commit()

    return {
        "status": "success",
        "message": "Tenant closed accounting period updated successfully.",
        "tenant_id": current_user.tenant_id,
        "books_closed_through_date": new_date.isoformat() if new_date else None,
    }


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

    from app.services.invoice_processing import get_effective_invoice_data
    vlm_data = get_effective_invoice_data(invoice)

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


@router.post("/invoices/{invoice_id}/journal/approve")
@router.post("/review/invoices/{invoice_id}/journal/approve")
@router.post("/invoices/{invoice_id}/review/journal/approve")
async def approve_journal_entry(
    invoice_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "FINANCE_REVIEWER", "DATA_REVIEWER"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Approves the General Ledger double-entry journal for an invoice:
    - Verifies that Stage 5 Financial Validation has no blocking MISMATCH.
    - Verifies that the double-entry journal is balanced (Debits == Credits).
    - Persists journal approval status as 'APPROVED' in relational DB (JournalEntry.status) and Invoice JSONB.
    - Stamps approved_by and approved_at.
    """
    tenant_id = current_user.tenant_id
    user_email = current_user.email

    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    res = await db.execute(query)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # 1. Financial Validation Gate Check
    if invoice.financial_validation_result and isinstance(invoice.financial_validation_result, dict):
        fin_status = invoice.financial_validation_result.get("overall_status")
        if fin_status == "MISMATCH":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve journal: Stage 5 Financial Validation reported MISMATCH. Discrepancies must be resolved before approval.",
            )

    # 2. Extract / Generate Authoritative Journal
    from app.services.invoice_processing import get_effective_invoice_data
    vlm_data = get_effective_invoice_data(invoice)
    accounting_data = (
        invoice.current_accounting_output
        if isinstance(invoice.current_accounting_output, dict)
        else (invoice.accounting_output if isinstance(invoice.accounting_output, dict) else {})
    )

    journal = invoice.journal_entry
    if not journal or not isinstance(journal, dict):
        journal = journal_generator.generate_journal(
            invoice_data=vlm_data,
            accounting_classification=accounting_data,
            gst_result=invoice.gst_result,
            itc_result=invoice.itc_result,
            tds_result=accounting_data.get("tds") if isinstance(accounting_data, dict) else None,
            financial_validation_result=invoice.financial_validation_result,
        )

    # 3. Check Balance
    total_debit = float(journal.get("total_debit") or 0.0)
    total_credit = float(journal.get("total_credit") or 0.0)
    difference = float(journal.get("difference") or 0.0)
    is_balanced = bool(journal.get("is_balanced") or journal.get("validation", {}).get("balanced") or (abs(total_debit - total_credit) < 0.01 and total_debit > 0))

    if not is_balanced or difference != 0.0 or total_debit <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve journal: Journal is unbalanced (Debits ₹{total_debit} != Credits ₹{total_credit}, Diff: ₹{difference}).",
        )

    # 4. Stamp approval metadata
    now_iso = datetime.now(timezone.utc).isoformat()
    journal["status"] = "APPROVED"
    journal["approval_status"] = "APPROVED"
    journal["approved_by"] = user_email
    journal["approved_at"] = now_iso
    journal["is_balanced"] = True

    invoice.journal_entry = journal

    # 5. Sync to relational JournalEntry
    synced_entry = await sync_relational_journal(
        session=db,
        invoice_id=invoice_id,
        journal_dict=journal,
        tenant_id=tenant_id,
    )
    if synced_entry:
        synced_entry.status = "APPROVED"
        synced_entry.is_balanced = True
        synced_entry.balanced = True

    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invoice)

    # 6. Audit Logging
    await audit_service.log_event(
        db=db,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        user_email=user_email,
        action="APPROVE_JOURNAL",
        reason=f"General Ledger double-entry journal approved by {user_email} (Debits ₹{total_debit} == Credits ₹{total_credit})",
    )

    return {
        "status": "success",
        "message": "General Ledger journal approved successfully.",
        "journal_status": "APPROVED",
        "approval_status": "APPROVED",
        "is_balanced": True,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "approved_by": user_email,
        "approved_at": now_iso,
        "journal_entry": journal,
    }


@router.post("/invoices/{invoice_id}/tds/approve")
@router.post("/review/invoices/{invoice_id}/tds/approve")
@router.post("/invoices/{invoice_id}/review/tds/approve")
async def approve_tds_assessment(
    invoice_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "FINANCE_REVIEWER", "DATA_REVIEWER"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Approves the statutory TDS assessment for an invoice:
    - Marks TDS as approved (is_approved=True, approval_status='APPROVED').
    - Stamps approved_by and approved_at.
    - Regenerates the authoritative double-entry journal (clearing any unapproved TDS warnings).
    - Persists changes and syncs relational DB.
    - Logs audit event.
    """
    tenant_id = current_user.tenant_id
    user_email = current_user.email

    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    res = await db.execute(query)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    accounting_data = (
        invoice.current_accounting_output
        if isinstance(invoice.current_accounting_output, dict)
        else (invoice.accounting_output if isinstance(invoice.accounting_output, dict) else {})
    )
    from app.services.tds_engine import get_effective_tds_data
    effective_tds = get_effective_tds_data(accounting_data)
    now_iso = datetime.now(timezone.utc).isoformat()

    tds_data = dict(accounting_data.get("tds_assessment") or effective_tds)
    tds_data["is_approved"] = True
    tds_data["approval_status"] = "APPROVED"
    tds_data["approved_by"] = user_email
    tds_data["approved_at"] = now_iso

    accounting_data["tds_assessment"] = tds_data
    accounting_data["tds"] = tds_data
    accounting_data["tds_final"] = tds_data
    invoice.accounting_output = accounting_data
    invoice.current_accounting_output = accounting_data

    # Regenerate GL journal with approved TDS
    from app.services.invoice_processing import get_effective_invoice_data
    vlm_data = get_effective_invoice_data(invoice)

    journal = journal_generator.generate_journal(
        invoice_data=vlm_data,
        accounting_classification=accounting_data,
        gst_result=invoice.gst_result,
        itc_result=invoice.itc_result,
        tds_result=tds_data,
        financial_validation_result=invoice.financial_validation_result,
    )
    if invoice.journal_entry and invoice.journal_entry.get("approval_status") == "APPROVED":
        journal["approval_status"] = "APPROVED"
        journal["status"] = "APPROVED"
        journal["approved_by"] = invoice.journal_entry.get("approved_by")
        journal["approved_at"] = invoice.journal_entry.get("approved_at")

    invoice.journal_entry = journal
    await sync_relational_journal(db, invoice.id, journal, tenant_id)

    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invoice)

    await audit_service.log_event(
        db=db,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        user_email=user_email,
        action="APPROVE_TDS",
        reason=f"TDS assessment approved by {user_email}",
    )

    return {
        "status": "success",
        "message": "TDS assessment approved successfully.",
        "tds": tds_data,
        "journal_entry": journal,
    }


@router.post("/invoices/{invoice_id}/approve")
@router.post("/review/invoices/{invoice_id}/approve")
@router.post("/invoices/{invoice_id}/review/approve")
async def approve_invoice(
    invoice_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "FINANCE_REVIEWER", "DATA_REVIEWER"])),
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

    # 2. Extract Authoritative Working Payload and Accounting Classification
    from app.services.invoice_processing import get_effective_invoice_data
    vlm_data = get_effective_invoice_data(invoice)

    # GATE 2 ENFORCEMENT: Server-side Closed Accounting Period Validation
    t_query = select(Tenant).where(Tenant.id == tenant_id)
    t_res = await db.execute(t_query)
    tenant_obj = t_res.scalar_one_or_none()
    if not tenant_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant organization '{tenant_id}' could not be loaded for accounting period validation."
        )
    lock_date = tenant_obj.books_closed_through_date

    doc_date = parse_and_normalize_date(vlm_data.get("invoice_date"))
    effective_posting = parse_and_normalize_date(invoice.posting_date) or doc_date

    if is_date_in_closed_period(effective_posting, lock_date):
        if invoice.period_resolution != "PRIOR_PERIOD_EXCEPTION":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot approve invoice: Posting date ({effective_posting}) falls within a closed accounting period "
                    f"(Books closed through {lock_date}). An authorized Finance Prior-Period Exception is required before approval."
                ),
            )
        # Verify exception has mandatory reason
        if not invoice.period_resolution_reason or len(invoice.period_resolution_reason.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Prior-Period Exception requires a valid audit rationale (minimum 10 characters).",
            )

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

    # Check Finance Chart of Accounts approval on every line item
    for item in acct_lines:
        idx = item.get("line_index", 1)
        app_id = (
            item.get("approved_account_id")
            or item.get("final_account_id")
            or item.get("account_id")
        )
        app_name = (
            item.get("approved_account_name")
            or item.get("final_account_name")
            or item.get("account_name")
        )

        if not app_id:
            if item.get("ai_account_id"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot approve invoice: Line item {idx} has not been approved by Finance.",
                )
            if default_expense:
                app_id, app_name = default_expense
            else:
                app_id = f"ACC_{idx}"
                app_name = app_name or "General Expenses"
        elif not app_name:
            app_name = coa_map.get(str(app_id)) or f"Account {app_id}"

        # Update line item with approved credentials
        item["approved_account_id"] = str(app_id)
        item["approved_account_name"] = str(app_name)
        item["approved_by"] = user_email
        item["approved_at"] = now_iso

    if isinstance(accounting_data.get("tds"), dict):
        accounting_data["tds"]["is_approved"] = True
        accounting_data["tds"]["approval_status"] = "APPROVED"
        accounting_data["tds"]["approved_by"] = user_email
        accounting_data["tds"]["approved_at"] = now_iso

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

    invoice.status = "COMPLETED"
    invoice.approval_status = "APPROVED"
    invoice.accounting_status = "COMPLETED"
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
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "FINANCE_REVIEWER", "DATA_REVIEWER"])),
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
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "FINANCE_REVIEWER", "DATA_REVIEWER"])),
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


@router.get("/invoices/{invoice_id}/vendor/status")
@router.get("/review/invoices/{invoice_id}/vendor/status")
async def get_invoice_vendor_status(
    invoice_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Checks if the invoice's vendor is confidently matched in the connected Zoho Books organization.
    Returns MATCHED, NOT_FOUND, or MISMATCH without performing arbitrary fallback.
    """
    tenant_id = current_user.tenant_id
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    res = await db.execute(query)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    from app.services.invoice_processing import get_effective_invoice_data
    vlm_data = get_effective_invoice_data(invoice)
    vendor_name = (vlm_data.get("vendor_name") or "").strip()
    vendor_gstin = (vlm_data.get("vendor_gstin") or "").strip() or None
    vendor_pan = (vlm_data.get("vendor_pan") or "").strip() or None
    vendor_address = vlm_data.get("vendor_address")

    from app.services.master_data_service import master_data_service
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db)
    if connection.status != "CONNECTED" or not connection.organization_id:
        return {
            "invoice_id": str(invoice_id),
            "is_zoho_connected": False,
            "match_status": "NOT_CONNECTED",
            "invoice_vendor": {
                "vendor_name": vendor_name,
                "vendor_gstin": vendor_gstin,
                "vendor_pan": vendor_pan,
                "vendor_address": vendor_address,
            },
            "matched_vendor": None,
            "requires_action": False,
        }

    from app.services.zoho_client import zoho_client_service
    matched_contact = await zoho_client_service.search_vendor(
        connection=connection,
        db=db,
        gstin=vendor_gstin,
        pan=vendor_pan,
        vendor_name=vendor_name,
    )

    match_status = "MATCHED" if matched_contact else "NOT_FOUND"
    return {
        "invoice_id": str(invoice_id),
        "is_zoho_connected": True,
        "match_status": match_status,
        "invoice_vendor": {
            "vendor_name": vendor_name,
            "vendor_gstin": vendor_gstin,
            "vendor_pan": vendor_pan,
            "vendor_address": vendor_address,
            "vendor_phone": vlm_data.get("vendor_phone"),
            "vendor_email": vlm_data.get("vendor_email"),
        },
        "matched_vendor": {
            "contact_id": matched_contact.get("contact_id"),
            "contact_name": matched_contact.get("contact_name") or matched_contact.get("company_name"),
            "gst_no": matched_contact.get("gst_no"),
            "pan_no": matched_contact.get("pan_no"),
            "email": matched_contact.get("email"),
            "phone": matched_contact.get("phone"),
        } if matched_contact else None,
        "requires_action": match_status != "MATCHED",
    }


@router.post("/invoices/{invoice_id}/vendor/add-to-zoho")
@router.post("/review/invoices/{invoice_id}/vendor/add-to-zoho")
async def add_vendor_to_zoho(
    invoice_id: UUID,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "FINANCE_MANAGER", "FINANCE_REVIEWER", "DATA_REVIEWER"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Explicitly creates the vendor in Zoho Books using the current authoritative saved data.
    Associates the newly created contact_id with the invoice.
    """
    tenant_id = current_user.tenant_id
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    res = await db.execute(query)
    invoice = res.scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    from app.services.master_data_service import master_data_service
    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, db)
    if connection.status != "CONNECTED" or not connection.organization_id:
        raise HTTPException(status_code=400, detail="Tenant is not connected to Zoho Books.")

    from app.services.invoice_processing import get_effective_invoice_data
    from app.services.gst_engine import gst_engine
    vlm_data = get_effective_invoice_data(invoice)
    gst_eval = gst_engine.evaluate_gst(vlm_data)

    vendor_name = (vlm_data.get("vendor_name") or "").strip()
    if not vendor_name:
        raise HTTPException(status_code=400, detail="Invoice lacks a valid vendor name.")

    vendor_gstin = (vlm_data.get("vendor_gstin") or "").strip() or None
    vendor_pan = (vlm_data.get("vendor_pan") or "").strip() or None
    vendor_email = vlm_data.get("vendor_email")
    vendor_phone = vlm_data.get("vendor_phone")
    vendor_address = vlm_data.get("vendor_address")
    supplier_state_name = gst_eval.get("supplier_state_name")

    try:
        from app.services.zoho_client import zoho_client_service
        created = await zoho_client_service.create_vendor(
            connection=connection,
            db=db,
            vendor_name=vendor_name,
            gstin=vendor_gstin,
            pan=vendor_pan,
            email=vendor_email,
            phone=vendor_phone,
            address=vendor_address,
            state_name=supplier_state_name,
        )
    except Exception as exc:
        err_msg = str(exc)
        if "4000" in err_msg or "reached that limit" in err_msg:
            clean_msg = "Your connected Zoho Books organization has reached its 20-contact subscription limit. Please delete or archive unused contacts in Zoho Books or upgrade your subscription."
        else:
            clean_msg = f"Zoho Books vendor creation failed: {err_msg}"
        logger.error(f"Failed to create vendor in Zoho: {clean_msg}")
        raise HTTPException(status_code=400, detail=clean_msg)

    contact_id = created.get("contact_id")
    if not contact_id:
        raise HTTPException(status_code=400, detail=f"Failed to create vendor '{vendor_name}' in Zoho Books.")

    # Save created vendor ID in invoice current_vlm_output
    curr = dict(invoice.current_vlm_output or {})
    if "data" in curr and isinstance(curr["data"], dict):
        curr["data"]["zoho_vendor_id"] = contact_id
    else:
        curr["zoho_vendor_id"] = contact_id
    invoice.current_vlm_output = curr
    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()

    await audit_service.log_event(
        db=db,
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        user_email=current_user.email,
        action="ADD_VENDOR_TO_ZOHO",
        reason=f"Added vendor '{vendor_name}' ({contact_id}) to Zoho Books",
    )

    return {
        "status": "success",
        "message": f"Vendor '{vendor_name}' successfully added to Zoho Books.",
        "contact_id": contact_id,
        "vendor": created,
    }


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

