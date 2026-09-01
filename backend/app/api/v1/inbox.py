import hashlib
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import Invoice, Integration
from app.core.config import settings
from app.storage.supabase_storage import storage_service
from app.services.imap_service import imap_service
from app.services.invoice_processing import process_invoice_background
from app.services.document_context import prepare_classification_context
from app.services.groq_classifier import classify_document, get_unknown_fallback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Inbox / Ingestion"])


@router.get("/inbox/staged")
async def get_staged_documents(db: AsyncSession = Depends(get_db)):
    """Retrieves all staged invoices waiting for review, excluding NOT_FINANCIAL records while preserving FINANCIAL, UNKNOWN, and legacy NULL records."""
    query = (
        select(Invoice)
        .where(
            Invoice.status == "STAGED",
            or_(
                Invoice.financial_relevance != "NOT_FINANCIAL",
                Invoice.financial_relevance.is_(None),
            ),
        )
        .order_by(Invoice.created_at.desc())
    )
    result = await db.execute(query)
    staged = result.scalars().all()
    return staged



@router.post("/inbox/staged/{invoice_id}/process")
async def process_staged_document(
    invoice_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Triggers invoice extraction and Stage 3 accounting pipeline for a staged document."""
    query = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staged invoice '{invoice_id}' not found.",
        )

    if invoice.status != "STAGED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice '{invoice_id}' has already been processed or is not in STAGED status.",
        )

    # Change status to PENDING
    invoice.status = "PENDING"
    await db.commit()
    await db.refresh(invoice)

    # Run full Qwen Stage 2 & Stage 3 parsing pipeline in background
    background_tasks.add_task(process_invoice_background, invoice_id)

    return {
        "success": True,
        "invoice_id": invoice.id,
        "status": invoice.status,
        "message": "Invoice successfully pushed to processing pipeline.",
    }


@router.delete("/inbox/staged/{invoice_id}")
async def delete_staged_document(
    invoice_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Deletes a staged invoice from the database instantly, cleaning up Supabase Storage in the background."""
    query = select(Invoice).where(Invoice.id == invoice_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staged invoice '{invoice_id}' not found.",
        )

    # Queue Supabase Storage deletion in the background to avoid blocking the API response
    if invoice.file_path:
        async def safe_delete_storage(path: str):
            try:
                await storage_service.delete_file(path)
            except Exception as e:
                logger.error(f"Failed to delete file '{path}' from storage in background: {e}")
                
        background_tasks.add_task(safe_delete_storage, invoice.file_path)

    # Delete database record instantly
    await db.delete(invoice)
    await db.commit()

    return {"success": True, "message": "Staged invoice deleted successfully."}


@router.post("/email/poll")
@router.post("/inbox/poll")
async def poll_email_inbox(window_hours: int = 24, db: AsyncSession = Depends(get_db)):
    """Triggers live polling of the configured IMAP mailbox to ingest new attachments."""
    import time
    start_total = time.perf_counter()
    
    # Find email config
    query = select(Integration).where(Integration.id == "imap_email")
    result = await db.execute(query)
    integration = result.scalar_one_or_none()

    if not integration or integration.status != "connected" or not integration.config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corporate email integration is not configured. Please connect your inbox in Settings.",
        )

    try:
        # Perform IMAP polling
        poll_res = await imap_service.poll_mailbox(integration.config, window_hours=window_hours)
    except Exception as e:
        err_msg = str(e)
        logger.error(f"IMAP Polling failed: {err_msg}")
        if "AUTHENTICATIONFAILED" in err_msg or "Invalid credentials" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="IMAP authentication failed. For Gmail accounts, please generate a 16-character Google App Password (https://myaccount.google.com/apppasswords) and update your credentials in the Integrations hub.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to poll mailbox: {err_msg}",
        )

    attachments = poll_res.get("attachments", [])
    parser_errors = poll_res.get("errors", [])
    emails_checked = poll_res.get("emails_checked", 0)
    attachments_found = poll_res.get("attachments_found", 0)
    imap_timings = poll_res.get("timings", {})
    
    new_documents = 0
    duplicates = 0
    failed_attachments = len(parser_errors)
    errors_list = list(parser_errors)

    # 1. Batch duplicate check query
    start_dup = time.perf_counter()
    hashes = [att["file_hash"] for att in attachments]
    existing_invoices = {}
    if hashes:
        dup_query = select(Invoice).where(Invoice.file_hash.in_(hashes))
        dup_result = await db.execute(dup_query)
        existing_invoices = {inv.file_hash: inv for inv in dup_result.scalars().all()}
    dup_time_ms = (time.perf_counter() - start_dup) * 1000.0

    # Filter out duplicates first
    unique_candidates = []
    for attachment in attachments:
        file_hash = attachment["file_hash"]
        logger.info(f"SHA256 = {file_hash}")
        
        existing_invoice = existing_invoices.get(file_hash)
        if existing_invoice:
            logger.info(f"DUPLICATE = YES | Existing ID: {existing_invoice.id} | Filename: {existing_invoice.file_name} | Status: {existing_invoice.status}")
            duplicates += 1
        else:
            logger.info("DUPLICATE = NO")
            unique_candidates.append(attachment)

    # 2. Concurrently upload unique attachments to Supabase Storage
    import asyncio
    import re
    
    async def upload_attachment_task(att):
        invoice_id = uuid.uuid4()
        clean_name = att["filename"]
        clean_name = re.sub(r"[^\w\.-]", "_", clean_name)[:100]
        storage_path = f"uploads/{invoice_id}_{clean_name}"
        
        try:
            await storage_service.upload_file(
                file_bytes=att["file_bytes"],
                file_path=storage_path,
                content_type=att["mime_type"],
            )
            return {
                "success": True,
                "attachment": att,
                "invoice_id": invoice_id,
                "storage_path": storage_path,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "attachment": att,
                "invoice_id": invoice_id,
                "storage_path": storage_path,
                "error": e
            }

    upload_time_ms = 0.0
    insert_time_ms = 0.0
    
    if unique_candidates:
        start_upload = time.perf_counter()
        logger.info(f"Concurrently uploading {len(unique_candidates)} unique files to Supabase...")
        upload_tasks = [upload_attachment_task(candidate) for candidate in unique_candidates]
        upload_results = await asyncio.gather(*upload_tasks)
        upload_time_ms = (time.perf_counter() - start_upload) * 1000.0
        
        # 3. Database inserts for successfully uploaded files
        start_insert = time.perf_counter()
        for res in upload_results:
            attachment = res["attachment"]
            invoice_id = res["invoice_id"]
            storage_path = res["storage_path"]
            
            if not res["success"]:
                err = res["error"]
                logger.error(f"STORAGE UPLOAD = FAIL | Filename: {attachment['filename']} | Exception: {str(err)}", exc_info=True)
                failed_attachments += 1
                errors_list.append({
                    "filename": attachment["filename"],
                    "reason": f"Supabase storage upload failed: {str(err)}"
                })
                continue
                
            logger.info("STORAGE UPLOAD = SUCCESS")
            
            # Prepare classification context and perform AI classification for unique attachment
            classification_res = None
            try:
                ctx = prepare_classification_context(attachment)
                classification_res = classify_document(ctx)
                logger.info(f"AI CLASSIFICATION = {classification_res.financial_relevance.value} | {classification_res.document_type.value}")
            except Exception as class_err:
                logger.error(f"Classification failed safely for {attachment['filename']}: {class_err}")
                classification_res = get_unknown_fallback(f"Classification failure: {class_err}")

            rel_val = classification_res.financial_relevance.value if hasattr(classification_res.financial_relevance, "value") else str(classification_res.financial_relevance)
            type_val = classification_res.document_type.value if hasattr(classification_res.document_type, "value") else str(classification_res.document_type)

            # Save record as STAGED invoice
            new_invoice = Invoice(
                id=invoice_id,
                file_path=storage_path,
                file_name=attachment["filename"],
                file_size=len(attachment["file_bytes"]),
                mime_type=attachment["mime_type"],
                file_hash=attachment["file_hash"],
                status="STAGED",
                accounting_status="STAGED",
                email_subject=attachment["email_subject"],
                email_sender=attachment["email_sender"],
                email_received_at=attachment["email_received_at"],
                email_message_id=attachment["email_message_id"],
                financial_relevance=rel_val,
                document_type=type_val,
                classification_confidence=classification_res.confidence,
                classification_reason=classification_res.reason,
                classification_model=getattr(settings, "GROQ_MODEL", "openai/gpt-oss-20b"),
            )
            try:
                db.add(new_invoice)
                await db.flush()
                new_documents += 1
                logger.info("DATABASE INSERT = SUCCESS")
            except Exception as e:
                logger.error(f"DATABASE INSERT = FAIL | Filename: {attachment['filename']} | Exception: {str(e)}", exc_info=True)
                failed_attachments += 1
                errors_list.append({
                    "filename": attachment["filename"],
                    "reason": f"Database insertion failed: {str(e)}"
                })
                # Clean up uploaded storage file if insertion fails
                try:
                    await storage_service.delete_file(storage_path)
                except Exception as cleanup_err:
                    logger.error(f"Failed to clean up storage file {storage_path}: {cleanup_err}")
                continue
        insert_time_ms = (time.perf_counter() - start_insert) * 1000.0

    # Update integration metadata
    integration.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    
    total_time_ms = (time.perf_counter() - start_total) * 1000.0
    
    # Print clear timing information
    logger.info("--- TOTAL POLLING PIPELINE TIMINGS ---")
    logger.info(f"IMAP connection/login: {imap_timings.get('imap_connection_login_ms', 0.0):.2f} ms")
    logger.info(f"IMAP search: {imap_timings.get('imap_search_ms', 0.0):.2f} ms")
    logger.info(f"Header fetching: {imap_timings.get('header_fetching_ms', 0.0):.2f} ms")
    logger.info(f"Full email fetching: {imap_timings.get('full_email_fetching_ms', 0.0):.2f} ms")
    logger.info(f"MIME parsing: {imap_timings.get('mime_parsing_ms', 0.0):.2f} ms")
    logger.info(f"Attachment extraction/download: {imap_timings.get('attachment_extraction_ms', 0.0):.2f} ms")
    logger.info(f"SHA-256 hashing: {imap_timings.get('sha256_hashing_ms', 0.0):.2f} ms")
    logger.info(f"Duplicate database query: {dup_time_ms:.2f} ms")
    logger.info(f"Supabase Storage upload: {upload_time_ms:.2f} ms")
    logger.info(f"Database insert: {insert_time_ms:.2f} ms")
    logger.info(f"TOTAL: {total_time_ms:.2f} ms")

    logger.info("POLL COMPLETE")

    return {
        "success": True,
        "emails_checked": emails_checked,
        "attachments_found": attachments_found,
        "accepted_attachments": len(attachments),
        "duplicates": duplicates,
        "new_documents": new_documents,
        "failed_attachments": failed_attachments,
        "errors": errors_list
    }
