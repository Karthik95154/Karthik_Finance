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
    db: AsyncSession = Depends(get_db),
):
    """Uploads an invoice to Supabase Storage, records initial metadata, and triggers background extraction pipeline."""
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

    invoice = Invoice(
        id=invoice_id,
        file_path=storage_path,
        file_name=original_name,
        file_size=file_size,
        mime_type=content_type,
        file_hash=file_hash,
        status="PENDING",
        accounting_status="PENDING",
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    # Dispatch asynchronous background extraction & accounting
    background_tasks.add_task(process_invoice_background, invoice.id)

    return InvoiceUploadResponse(
        invoice_id=invoice.id,
        file_name=invoice.file_name,
        file_size=invoice.file_size,
        mime_type=invoice.mime_type,
        file_hash=invoice.file_hash,
        status=invoice.status,
        created_at=invoice.created_at,
    )


@router.post(
    "/{invoice_id}/categorize",
    response_model=InvoiceStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def categorize_invoice_accounting(
    invoice_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers Stage 3 (Qwen3-4B Accounting & TDS reasoning) on an existing invoice
    using its current extraction JSON. Does NOT rerun Qwen3-VL.
    """
    query = select(Invoice).where(Invoice.id == invoice_id)
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
    await db.refresh(invoice)

    background_tasks.add_task(process_accounting_only_background, invoice.id)

    return InvoiceStatusResponse(
        invoice_id=invoice.id,
        status=invoice.status,
        accounting_status=invoice.accounting_status,
        error_message=invoice.error_message,
        confidence_score=invoice.confidence_score,
        accounting_confidence=invoice.accounting_confidence,
        updated_at=invoice.updated_at,
    )


@router.get("", response_model=list[InvoiceListItemResponse])
async def list_invoices(
    db: AsyncSession = Depends(get_db),
):
    """Lists all invoices ordered by creation date descending for workflow tracking."""
    query = select(Invoice).order_by(Invoice.created_at.desc())
    result = await db.execute(query)
    invoices = result.scalars().all()

    items = []
    for inv in invoices:
        vlm = inv.current_vlm_output or inv.raw_vlm_output or {}
        data = vlm.get("data") if isinstance(vlm, dict) else {}
        if not isinstance(data, dict):
            data = {}
        items.append(
            InvoiceListItemResponse(
                id=inv.id,
                file_name=inv.file_name,
                file_size=inv.file_size,
                mime_type=inv.mime_type,
                status=inv.status,
                accounting_status=inv.accounting_status,
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
    db: AsyncSession = Depends(get_db),
):
    """Lightweight polling endpoint for tracking invoice processing status."""
    query = select(Invoice).where(Invoice.id == invoice_id)
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
        error_message=invoice.error_message,
        confidence_score=invoice.confidence_score,
        accounting_confidence=invoice.accounting_confidence,
        updated_at=invoice.updated_at,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full stored invoice metadata including complete raw_vlm_output, current_vlm_output, and accounting_output."""
    query = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found.",
        )

    return invoice


@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice_extraction(
    invoice_id: uuid.UUID,
    update_data: InvoiceUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Saves user-edited invoice values into current_vlm_output and current_accounting_output while preserving raw outputs."""
    query = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice with ID {invoice_id} not found.",
        )

    if update_data.current_vlm_output is not None:
        invoice.current_vlm_output = update_data.current_vlm_output
    if update_data.current_accounting_output is not None:
        invoice.current_accounting_output = update_data.current_accounting_output

    invoice.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(invoice)

    return invoice


@router.get("/{invoice_id}/file")
async def get_invoice_file(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Streams the original unmodified file for in-browser rendering."""
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

    return Response(
        content=content,
        media_type=invoice.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{invoice.file_name}"',
            "Cache-Control": "public, max-age=3600",
        },
    )

