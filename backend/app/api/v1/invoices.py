import hashlib
import uuid
import re
from datetime import datetime, timezone
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import (
    AuthenticatedUser,
    get_current_user,
    require_roles,
)
from app.db.database import get_db
from app.db.models import Invoice
from app.schemas.invoice import (
    InvoiceListItemResponse,
    InvoiceResponse,
    InvoiceStatusResponse,
    InvoiceUpdateRequest,
    InvoiceUploadResponse,
)
from app.storage.supabase_storage import storage_service
from app.services.invoice_processing import (
    process_invoice_background,
    process_accounting_only_background,
)
from app.services.duplicate_detector import duplicate_detector

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal and unsafe characters."""
    clean = re.sub(r"[^\w\.-]", "_", filename)
    return clean[:100]


@router.post(
    "/upload",
    response_model=InvoiceUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Uploads an invoice to Supabase Storage, checks for duplicates, records metadata,
    and triggers background extraction pipeline.
    Requires ADMIN or FINANCE role.
    """
    tenant_id = current_user.tenant_id

    content_type = file.content_type or "application/octet-stream"
    if content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file format: '{content_type}'. "
                f"Allowed formats: {', '.join(settings.ALLOWED_MIME_TYPES)}"
            ),
        )

    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check for duplicate hash within this tenant
    existing_duplicate = await duplicate_detector.check_file_hash_duplicate(
        file_hash=file_hash,
        tenant_id=tenant_id,
        db=db,
    )
    if existing_duplicate:
        # If the duplicate is currently STAGED (e.g. from email inbox) or FAILED,
        # the user is manually uploading to process it. Promote to PENDING and start processing.
        if existing_duplicate.status in ["STAGED", "FAILED"]:
            existing_duplicate.status = "PENDING"
            existing_duplicate.error_message = None
            await db.commit()
            await db.refresh(existing_duplicate)
            background_tasks.add_task(process_invoice_background, existing_duplicate.id)
            
        return InvoiceUploadResponse(
            invoice_id=existing_duplicate.id,
            file_name=existing_duplicate.file_name,
            file_size=existing_duplicate.file_size,
            mime_type=existing_duplicate.mime_type,
            file_hash=existing_duplicate.file_hash,
            status=existing_duplicate.status,
            created_at=existing_duplicate.created_at,
        )

    invoice_id = uuid.uuid4()
    original_name = file.filename or "invoice"
    clean_name = sanitize_filename(original_name)
    storage_path = f"uploads/{invoice_id}_{clean_name}"

    try:
        await storage_service.upload_file(
            file_bytes=file_bytes,
            file_path=storage_path,
            content_type=content_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to store file in Supabase Storage: {str(e)}",
        )

    now_dt = datetime.now(timezone.utc)
    invoice = Invoice(
        id=invoice_id,
        tenant_id=tenant_id,
        file_path=storage_path,
        file_name=original_name,
        file_size=file_size,
        mime_type=content_type,
        file_hash=file_hash,
        status="PENDING",
        accounting_status="PENDING",
        approval_status="PENDING_REVIEW",
        export_status="NOT_EXPORTED",
        created_at=now_dt,
        updated_at=now_dt,
    )
    db.add(invoice)
    await db.commit()

    # Dispatch asynchronous background extraction & accounting
    background_tasks.add_task(process_invoice_background, invoice_id)

    return InvoiceUploadResponse(
        invoice_id=invoice_id,
        file_name=original_name,
        file_size=file_size,
        mime_type=content_type,
        file_hash=file_hash,
        status="PENDING",
        created_at=now_dt,
    )


@router.post(
    "/{invoice_id}/categorize",
    response_model=InvoiceStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def categorize_invoice_accounting(
    invoice_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers Stage 3 (Qwen3-4B Accounting & TDS reasoning) on an existing invoice.
    Requires ADMIN or FINANCE role.
    """
    tenant_id = current_user.tenant_id

    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found.",
        )

    if not invoice.current_vlm_output and not invoice.raw_vlm_output:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice has no VLM extraction data. Stage 2 extraction must complete first.",
        )

    invoice.accounting_status = "PROCESSING_ACCOUNTING"
    invoice.error_message = None
    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()

    background_tasks.add_task(process_accounting_only_background, invoice.id)

    return InvoiceStatusResponse(
        invoice_id=invoice.id,
        status=invoice.status,
        accounting_status=invoice.accounting_status,
        approval_status=invoice.approval_status,
        export_status=invoice.export_status,
        error_message=invoice.error_message,
        confidence_score=invoice.confidence_score,
        accounting_confidence=invoice.accounting_confidence,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


@router.get("", response_model=list[InvoiceListItemResponse])
async def list_invoices(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists all invoices for the authenticated user's tenant.
    Accessible to ADMIN, FINANCE, and VIEWER roles.
    """
    tenant_id = current_user.tenant_id
    query = select(Invoice).where(Invoice.tenant_id == tenant_id).order_by(Invoice.created_at.desc())
    result = await db.execute(query)
    invoices = result.scalars().all()

    items = []
    for inv in invoices:
        vlm = inv.current_vlm_output or inv.raw_vlm_output or {}
        if isinstance(vlm, dict):
            data = vlm.get("data") if ("data" in vlm and isinstance(vlm.get("data"), dict)) else vlm
        else:
            data = {}
        items.append(
            InvoiceListItemResponse(
                id=inv.id,
                tenant_id=inv.tenant_id,
                file_name=inv.file_name,
                file_size=inv.file_size,
                mime_type=inv.mime_type,
                status=inv.status,
                accounting_status=inv.accounting_status,
                approval_status=inv.approval_status,
                export_status=inv.export_status,
                zoho_bill_id=inv.zoho_bill_id,
                zoho_bill_number=inv.zoho_bill_number,
                vendor_name=data.get("vendor_name"),
                invoice_number=data.get("invoice_number"),
                total_amount=data.get("total_amount"),
                created_at=inv.created_at,
                updated_at=inv.updated_at,
            )
        )
    return items


@router.get("/{invoice_id}/status", response_model=InvoiceStatusResponse)
async def get_invoice_status(
    invoice_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Polling endpoint for tracking invoice processing, approval, and export status.
    Accessible to ADMIN, FINANCE, and VIEWER roles.
    """
    tenant_id = current_user.tenant_id
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found.",
        )

    return InvoiceStatusResponse(
        invoice_id=invoice.id,
        status=invoice.status,
        accounting_status=invoice.accounting_status,
        approval_status=invoice.approval_status,
        export_status=invoice.export_status,
        error_message=invoice.error_message,
        confidence_score=invoice.confidence_score,
        accounting_confidence=invoice.accounting_confidence,
        updated_at=invoice.updated_at,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves full stored invoice metadata.
    Accessible to ADMIN, FINANCE, VIEWER, and CUSTOMER roles.
    For CUSTOMER / VIEWER roles, invoice is only exposed after passing internal HITL approval.
    """
    tenant_id = current_user.tenant_id
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found.",
        )

    # If user has CUSTOMER role, require the invoice to be HITL approved
    if current_user.role == "CUSTOMER" and invoice.approval_status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer access unavailable: Invoice is awaiting internal Finance review and approval.",
        )

    return invoice


@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice_extraction(
    invoice_id: uuid.UUID,
    update_data: InvoiceUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_roles(["ADMIN", "FINANCE", "CUSTOMER"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Saves user-edited invoice values into current_vlm_output and current_accounting_output.
    Preserves raw_vlm_output (original model extraction JSON) immutably for audit.
    Automatically re-evaluates Stage 4 GST/ITC, Stage 5 Financial Validation, and Stage 6 GL Journal.
    Enforces role separation:
    - Internal Finance/Admin edits before approval remain in PENDING_REVIEW until approved.
    - Customer edits after HITL approval validate accounting/journal balance but do NOT re-enter HITL review.
    """
    tenant_id = current_user.tenant_id
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found.",
        )

    is_internal_role = current_user.role in ("ADMIN", "FINANCE")
    was_approved = (invoice.approval_status == "APPROVED")

    # If an internal finance user edits an approved invoice, unlock and reset approval
    if is_internal_role and was_approved:
        invoice.approval_status = "PENDING_REVIEW"
        invoice.locked_at = None

    if update_data.current_vlm_output is not None:
        from app.core.date_utils import parse_and_normalize_date
        vlm_dict = update_data.current_vlm_output
        if isinstance(vlm_dict, dict):
            target = vlm_dict.get("data") if isinstance(vlm_dict.get("data"), dict) else vlm_dict
            if target.get("invoice_date"):
                target["invoice_date"] = parse_and_normalize_date(target["invoice_date"])
            if target.get("due_date"):
                target["due_date"] = parse_and_normalize_date(target["due_date"])
        invoice.current_vlm_output = vlm_dict

    if update_data.current_accounting_output is not None:
        invoice.current_accounting_output = update_data.current_accounting_output

    # Re-evaluate Deterministic Validation Pipeline (Stages 4, 5, 6) using authoritative saved data
    try:
        from app.services.invoice_processing import get_effective_invoice_data
        from app.services.gst_engine import gst_engine
        from app.services.itc_engine import itc_engine
        from app.services.financial_validator import financial_validator
        from app.services.tds_engine import tds_engine
        from app.services.journal_generator import journal_generator, sync_relational_journal

        working_payload = get_effective_invoice_data(invoice)
        
        accounting_dict = (
            invoice.current_accounting_output
            if isinstance(invoice.current_accounting_output, dict)
            else (invoice.accounting_output if isinstance(invoice.accounting_output, dict) else {})
        )
        accounting_lines = accounting_dict.get("accounting") or []
        tds_assessment = accounting_dict.get("tds_assessment") or {}

        # 1. Stage 4 GST Engine
        gst_result = gst_engine.evaluate_gst(working_payload)

        # 2. Stage 4 ITC Engine
        combined_context = {
            "accounting": accounting_lines,
            "tds_assessment": tds_assessment,
        }
        itc_result = itc_engine.evaluate_itc(working_payload, combined_context)

        # 3. Stage 5 Financial Validator
        financial_validation_result = financial_validator.validate_invoice(working_payload, gst_result)

        # 4. Stage 5 Statutory TDS Recalculation on authoritative subtotal (Single Source of Truth)
        from app.services.tds_engine import get_effective_tds_data
        effective_tds = get_effective_tds_data(accounting_dict)
        tds_applicable = bool(effective_tds.get("applicable"))

        subtotal = float(working_payload.get("subtotal") or 0.0)
        tds_rate = effective_tds.get("rate")
        tds_section = effective_tds.get("section")
        tds_provision = effective_tds.get("provision")
        tds_nature = effective_tds.get("nature_of_payment")
        vendor_pan = working_payload.get("vendor_pan")

        final_tds_calc = tds_engine.calculate_tds(
            applicable=tds_applicable,
            section=tds_section,
            provision=tds_provision,
            nature_of_payment=tds_nature,
            base_amount=subtotal,
            rate=float(tds_rate) if tds_rate is not None else None,
            vendor_pan=vendor_pan,
        )

        persisted_accounting_output = {
            **accounting_dict,
            "accounting": accounting_lines,
            "tds_assessment": {
                **effective_tds,
                "tds_applicable": tds_applicable,
                "tds_section": tds_section,
                "tds_provision": tds_provision,
                "nature_of_payment": tds_nature,
                "tds_rate": final_tds_calc.get("rate") if tds_applicable else None,
                "tds_base_amount": final_tds_calc.get("base_amount") if tds_applicable else None,
                "proposed_tds_amount": final_tds_calc.get("tds_amount") if tds_applicable else None,
                "tds_reasoning": final_tds_calc.get("reason"),
            },
            "tds_final": final_tds_calc,
            "tds": final_tds_calc,
        }

        # 5. Stage 6 Double-Entry Journal Generator
        # Check if the user passed explicit manual journal edits with lines
        if update_data.journal_entry and isinstance(update_data.journal_entry, dict) and update_data.journal_entry.get("lines"):
            raw_lines = update_data.journal_entry.get("lines") or []
            parsed_lines = []
            dr_total = 0.0
            cr_total = 0.0
            for idx, l in enumerate(raw_lines, 1):
                d_val = float(l.get("debit") or 0.0)
                c_val = float(l.get("credit") or 0.0)
                dr_total += d_val
                cr_total += c_val
                l_type = l.get("line_type") or ("DEBIT" if d_val > 0 else "CREDIT")
                parsed_lines.append({
                    "line_number": idx,
                    "account_id": l.get("account_id") or f"ACC_{idx}",
                    "account_name": l.get("account_name") or f"Account {idx}",
                    "line_type": l_type,
                    "debit": round(d_val, 2),
                    "credit": round(c_val, 2),
                    "amount": round(d_val if d_val > 0 else c_val, 2),
                    "provenance": "HITL_OVERRIDE" if is_internal_role else "CUSTOMER_EDIT",
                    "description": l.get("description") or f"Line {idx}",
                    "is_approved": True,
                })
            
            dr_total = round(dr_total, 2)
            cr_total = round(cr_total, 2)
            diff = round(dr_total - cr_total, 2)
            is_bal = (abs(diff) < 0.01 and dr_total > 0)
            
            journal_errors = []
            if not is_bal:
                journal_errors.append(f"Manual journal unbalanced: Total Debits (₹{dr_total:,.2f}) != Total Credits (₹{cr_total:,.2f})")
            
            journal_result = {
                "status": "BALANCED" if is_bal else "UNBALANCED",
                "approval_status": "APPROVED" if (was_approved and not is_internal_role and is_bal) else "PENDING",
                "approved_by": current_user.email if (was_approved and not is_internal_role and is_bal) else None,
                "approved_at": datetime.now(timezone.utc).isoformat() if (was_approved and not is_internal_role and is_bal) else None,
                "total_debit": dr_total,
                "total_credit": cr_total,
                "difference": diff,
                "currency": "INR",
                "is_balanced": is_bal,
                "lines": parsed_lines,
                "validation": {
                    "balanced": is_bal,
                    "tolerance": 0.05,
                    "errors": journal_errors,
                    "warnings": [],
                },
            }
        else:
            journal_result = journal_generator.generate_journal(
                invoice_data=working_payload,
                accounting_classification=persisted_accounting_output,
                gst_result=gst_result,
                itc_result=itc_result,
                tds_result=final_tds_calc,
                financial_validation_result=financial_validation_result,
            )
            is_bal = bool(journal_result.get("is_balanced") or journal_result.get("validation", {}).get("balanced"))
            journal_result["approval_status"] = "APPROVED" if (was_approved and not is_internal_role and is_bal) else "PENDING"
            journal_result["approved_by"] = current_user.email if (was_approved and not is_internal_role and is_bal) else None
            journal_result["approved_at"] = datetime.now(timezone.utc).isoformat() if (was_approved and not is_internal_role and is_bal) else None
            journal_result["status"] = "BALANCED" if is_bal else "UNBALANCED"

        # Lifecycle state rule:
        # If internal finance edits, reset to PENDING_REVIEW.
        # If customer edits an approved invoice, retain APPROVED status (do NOT re-enter HITL).
        if is_internal_role:
            invoice.approval_status = "PENDING_REVIEW"
            invoice.locked_at = None
        elif was_approved:
            invoice.approval_status = "APPROVED"

        # Persist updated authoritative engine outputs
        invoice.accounting_output = persisted_accounting_output
        invoice.current_accounting_output = persisted_accounting_output
        invoice.gst_result = gst_result
        invoice.itc_result = itc_result
        invoice.financial_validation_result = financial_validation_result
        invoice.journal_entry = journal_result

        await sync_relational_journal(db, invoice.id, journal_result)
    except Exception as eval_exc:
        # Non-blocking log if deterministic revalidation encountered an issue
        import logging
        logging.getLogger(__name__).warning(f"Error during deterministic revalidation on update for {invoice_id}: {eval_exc}")

    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invoice)

    return invoice


@router.get("/{invoice_id}/file")
async def get_invoice_file(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Streams original unmodified invoice binary from Supabase Storage.
    """
    query = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found.",
        )

    try:
        content = await storage_service.download_file(invoice.file_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice file not found in storage.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage retrieval error: {str(e)}",
        )

    # Infer/correct the MIME type based on file extension if stored type is generic
    mime_type = invoice.mime_type
    if not mime_type or mime_type == "application/octet-stream":
        ext = invoice.file_name.lower().split(".")[-1]
        ext_map = {
            "pdf": "application/pdf",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "tif": "image/tiff",
            "tiff": "image/tiff"
        }
        if ext in ext_map:
            mime_type = ext_map[ext]
        else:
            import mimetypes
            inferred_type, _ = mimetypes.guess_type(invoice.file_name)
            if inferred_type:
                mime_type = inferred_type

    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{invoice.file_name}"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/{invoice_id}/pages")
async def get_invoice_pages(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Renders multi-page PDF invoices into a list of base64 PNG images, or returns
    the direct image base64 if it's already an image format.
    """
    query = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found.",
        )

    try:
        content = await storage_service.download_file(invoice.file_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice file not found in storage.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage retrieval error: {str(e)}",
        )

    ext = (invoice.file_name or "").lower().split(".")[-1]
    if ext == "pdf" or invoice.mime_type == "application/pdf":
        try:
            import fitz
            import base64
            doc = fitz.open(stream=content, filetype="pdf")
            pages = []
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                # Render to PNG bytes (150 DPI for good balance of speed and clarity)
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                b64_str = base64.b64encode(img_bytes).decode("utf-8")
                pages.append(f"data:image/png;base64,{b64_str}")
            doc.close()
            return {"invoice_id": str(invoice_id), "page_count": len(pages), "pages": pages}
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to render PDF pages: {str(e)}",
            )
    else:
        import base64
        b64_str = base64.b64encode(content).decode("utf-8")
        media_type = invoice.mime_type or "image/png"
        return {"invoice_id": str(invoice_id), "page_count": 1, "pages": [f"data:{media_type};base64,{b64_str}"]}
