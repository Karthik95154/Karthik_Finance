import hashlib
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, or_, and_, true, false
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import Invoice, Integration, EmailConnection
from app.core.config import settings
from app.core.security import AuthenticatedUser, get_current_user
from app.storage.supabase_storage import storage_service
from app.services.imap_service import imap_service
from app.services.invoice_processing import process_invoice_background
from app.services.document_context import prepare_classification_context
from app.services.groq_classifier import classify_document, get_unknown_fallback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Inbox / Ingestion"])


def get_user_filter(current_user: AuthenticatedUser):
    try:
        user_uuid = uuid.UUID(current_user.id)
        return (Invoice.user_id == user_uuid)
    except (ValueError, TypeError):
        return false()



@router.get("/inbox/staged")
async def get_staged_documents(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves staged invoices waiting for review belonging strictly to the authenticated user."""
    try:
        user_uuid = uuid.UUID(current_user.id)
        user_filter = (Invoice.user_id == user_uuid)
    except (ValueError, TypeError):
        user_filter = false()

    query = (
        select(Invoice)
        .where(
            Invoice.status == "STAGED",
            user_filter,
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
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Triggers invoice extraction and Stage 3 accounting pipeline for a staged document."""
    try:
        user_uuid = uuid.UUID(current_user.id)
        user_filter = (Invoice.user_id == user_uuid)
    except (ValueError, TypeError):
        user_filter = false()

    query = select(Invoice).where(Invoice.id == invoice_id, user_filter)
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
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a staged invoice from the database instantly, cleaning up Supabase Storage in the background."""
    try:
        user_uuid = uuid.UUID(current_user.id)
        user_filter = (Invoice.user_id == user_uuid)
    except (ValueError, TypeError):
        user_filter = false()

    query = select(Invoice).where(Invoice.id == invoice_id, user_filter)
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
async def poll_email_inbox(
    window_hours: int = 24,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Triggers live polling of the configured EmailConnection mailbox to ingest new attachments.

    Polling mode is determined automatically from the user's EmailConnection record:
      - INITIAL POLL  : last_successful_poll_at IS NULL  → uses existing window_hours lookback
      - INCREMENTAL   : last_successful_poll_at IS SET   → fetches only emails after that timestamp

    The poll_upper_bound is captured at the START of the request so that emails arriving
    while polling is in progress are correctly included in the next poll window.

    last_successful_poll_at is updated ONLY after the entire poll succeeds.
    On IMAP failure or unexpected error the checkpoint is NOT advanced.
    """
    import time
    import asyncio
    import re
    start_total = time.perf_counter()

    # ── 1. Resolve user UUID and EmailConnection filter ──────────────────────
    try:
        current_user_uuid = uuid.UUID(current_user.id)
        user_conn_filter = or_(
            EmailConnection.user_id == current_user_uuid,
            EmailConnection.user_id_str == str(current_user.id),
        )
    except (ValueError, TypeError):
        current_user_uuid = None
        user_conn_filter = (EmailConnection.user_id_str == str(current_user.id))

    # Find EmailConnection record for this specific user strictly (NO cross-user global fallbacks)
    query = select(EmailConnection).where(user_conn_filter, EmailConnection.is_active == True)
    result = await db.execute(query)
    email_conn = result.scalars().first()

    if not email_conn:
        logger.warning(f"POLL DENIED: No active EmailConnection found for user_id={current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email account is connected. Please connect an email account first in Settings.",
        )

    # ── 2. Concurrent-poll guard (lightweight mutex via is_polling flag) ─────
    if email_conn.is_polling:
        logger.warning(f"POLL DENIED: Concurrent poll already in progress for user_id={current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A poll is already in progress for this email account. Please wait for it to complete.",
        )

    # ── 3. Capture poll_upper_bound BEFORE any IMAP call ────────────────────
    # This guarantees emails arriving while we are polling are included in the NEXT window.
    poll_upper_bound = datetime.now(timezone.utc)

    # ── 4. Determine polling mode ────────────────────────────────────────────
    since_datetime = email_conn.last_successful_poll_at  # None = first / initial poll
    is_first_poll = since_datetime is None
    poll_mode = "initial" if is_first_poll else "incremental"

    configured_email = email_conn.email_address
    masked_email = configured_email[0] + "***@" + configured_email.split("@")[-1] if "@" in configured_email else "***"
    logger.info(
        f"POLL INITIATED | mode={poll_mode} | User ID: {current_user.id} | "
        f"EmailConnection ID: {email_conn.id} | Mailbox: {masked_email} | "
        f"since={since_datetime.isoformat() if since_datetime else 'N/A'} | "
        f"upper_bound={poll_upper_bound.isoformat()}"
    )

    imap_config = {
        "imap_server": email_conn.imap_host,
        "imap_port": email_conn.imap_port,
        "email_address": email_conn.email_address,
        "password": email_conn.encrypted_password,
    }

    # ── 5. Set is_polling mutex; always release in finally ───────────────────
    email_conn.is_polling = True
    await db.commit()

    poll_successful = False
    try:
        # ── 6. Perform IMAP polling ──────────────────────────────────────────
        # Pass since_datetime=None for initial poll (uses window_hours lookback).
        # Pass since_datetime=last_successful_poll_at for incremental poll.
        try:
            poll_res = await imap_service.poll_mailbox(
                imap_config,
                window_hours=window_hours,
                since_datetime=since_datetime,
            )
        except Exception as e:
            err_msg = str(e)
            logger.error(f"IMAP Polling failed for user {current_user.id}: {err_msg}")
            if "AUTHENTICATIONFAILED" in err_msg or "Invalid credentials" in err_msg:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Unable to authenticate with the connected email account: {err_msg}",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"IMAP Polling error: {err_msg}",
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

        # ── 7. SHA-256 duplicate detection (user-scoped) ─────────────────────
        # This is the secondary safety net — it catches duplicates even if IMAP
        # overlaps return the same attachment in multiple polling windows.
        start_dup = time.perf_counter()
        hashes = [att["file_hash"] for att in attachments]
        existing_invoices = {}
        if hashes:
            if current_user_uuid:
                user_inv_filter = (Invoice.user_id == current_user_uuid)
            else:
                user_inv_filter = false()

            dup_query = select(Invoice).where(user_inv_filter, Invoice.file_hash.in_(hashes))
            dup_result = await db.execute(dup_query)
            existing_invoices = {inv.file_hash: inv for inv in dup_result.scalars().all()}
        dup_time_ms = (time.perf_counter() - start_dup) * 1000.0

        # Filter out duplicates first
        unique_candidates = []
        for attachment in attachments:
            file_hash = attachment["file_hash"]
            logger.info(f"SHA256 = {file_hash} for User = {current_user.id}")

            existing_invoice = existing_invoices.get(file_hash)
            if existing_invoice:
                logger.info(f"DUPLICATE FOR USER = YES | Existing Invoice ID: {existing_invoice.id} | Filename: {existing_invoice.file_name}")
                duplicates += 1
            else:
                logger.info(f"DUPLICATE FOR USER = NO | Filename: {attachment['filename']}")
                unique_candidates.append(attachment)

        # ── 8. Classify and store unique financial documents ─────────────────
        # Non-financial documents are discarded here and NOT stored in the Invoice
        # table. The incremental checkpoint prevents them from being re-fetched.
        upload_time_ms = 0.0
        insert_time_ms = 0.0

        if unique_candidates:
            for attachment in unique_candidates:
                # Step A: AI visual classification FIRST — before any storage/DB write
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

                # Accept INVOICE, CREDIT_NOTE, DEBIT_NOTE, or UNKNOWN fallback
                allowed_document_types = {"INVOICE", "CREDIT_NOTE", "DEBIT_NOTE", "UNKNOWN"}
                is_financial_doc = (type_val in allowed_document_types) or (rel_val in ("FINANCIAL", "UNKNOWN"))

                if not is_financial_doc:
                    # Non-financial: discard. Do NOT create an Invoice record.
                    # The incremental checkpoint will prevent this attachment from
                    # being fetched and classified again on the next poll.
                    logger.info(f"NON-FINANCIAL DOCUMENT DISCARDED | Type: {type_val} | Relevance: {rel_val} | Filename: {attachment['filename']}")
                    continue

                # Step B: Upload financial document to Supabase Storage
                invoice_id = uuid.uuid4()
                clean_name = attachment["filename"]
                clean_name = re.sub(r"[^\w\.-]", "_", clean_name)[:100]
                storage_path = f"uploads/{invoice_id}_{clean_name}"

                start_upload = time.perf_counter()
                try:
                    await storage_service.upload_file(
                        file_bytes=attachment["file_bytes"],
                        file_path=storage_path,
                        content_type=attachment["mime_type"],
                    )
                    upload_time_ms += (time.perf_counter() - start_upload) * 1000.0
                    logger.info("STORAGE UPLOAD = SUCCESS")
                except Exception as e:
                    logger.error(f"STORAGE UPLOAD = FAIL | Filename: {attachment['filename']} | Exception: {str(e)}", exc_info=True)
                    failed_attachments += 1
                    errors_list.append({
                        "filename": attachment["filename"],
                        "reason": f"Supabase storage upload failed: {str(e)}"
                    })
                    continue

                # Step C: Save STAGED invoice record in PostgreSQL
                start_insert = time.perf_counter()
                new_invoice = Invoice(
                    id=invoice_id,
                    tenant_id=current_user.tenant_id,
                    user_id=current_user_uuid,
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
                    classification_model=getattr(settings, "GROQ_MODEL", "qwen/qwen3.8-27b"),
                )
                try:
                    db.add(new_invoice)
                    await db.flush()
                    new_documents += 1
                    insert_time_ms += (time.perf_counter() - start_insert) * 1000.0
                    logger.info("DATABASE INSERT = SUCCESS")
                except Exception as e:
                    logger.error(f"DATABASE INSERT = FAIL | Filename: {attachment['filename']} | Exception: {str(e)}", exc_info=True)
                    failed_attachments += 1
                    errors_list.append({
                        "filename": attachment["filename"],
                        "reason": f"Database insertion failed: {str(e)}"
                    })
                    try:
                        await storage_service.delete_file(storage_path)
                    except Exception as cleanup_err:
                        logger.error(f"Failed to clean up storage file {storage_path}: {cleanup_err}")
                    continue

        # ── 9. Advance checkpoint ONLY after successful processing ────────────
        # This is the core incremental polling invariant.
        # poll_upper_bound was captured at the start of the request, so emails
        # arriving during this poll will be fetched by the next poll window.
        now_utc = datetime.now(timezone.utc)
        email_conn.last_synced_at = now_utc
        email_conn.last_successful_poll_at = poll_upper_bound
        if is_first_poll:
            # First manual poll just completed → enable automatic 7AM polling
            email_conn.automatic_polling_enabled = True
            logger.info(f"FIRST POLL COMPLETE | automatic_polling_enabled=True for user {current_user.id}")
        email_conn.is_polling = False
        await db.commit()
        poll_successful = True

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
        logger.info(f"POLL COMPLETE | mode={poll_mode} | checkpoint_advanced_to={poll_upper_bound.isoformat()}")

        return {
            "success": True,
            "poll_mode": poll_mode,
            "poll_since": since_datetime.isoformat() if since_datetime else None,
            "poll_upper_bound": poll_upper_bound.isoformat(),
            "emails_checked": emails_checked,
            "attachments_found": attachments_found,
            "accepted_attachments": len(attachments),
            "duplicates": duplicates,
            "new_documents": new_documents,
            "failed_attachments": failed_attachments,
            "errors": errors_list,
        }

    finally:
        # ── 10. Always release the mutex, even if an exception propagated ─────
        if not poll_successful:
            try:
                email_conn.is_polling = False
                await db.commit()
            except Exception as mutex_err:
                logger.error(f"Failed to release is_polling mutex for user {current_user.id}: {mutex_err}")
