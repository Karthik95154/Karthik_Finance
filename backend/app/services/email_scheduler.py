"""
email_scheduler.py
Daily 7:00 AM UTC automatic email polling scheduler.

Uses APScheduler (AsyncIOScheduler) integrated with FastAPI lifespan.

Design decisions:
  - Runs at 07:00 UTC every day.
  - Only polls users where automatic_polling_enabled = TRUE and
    last_successful_poll_at IS NOT NULL.
  - Each user is polled independently; one user failure does not affect others.
  - Respects the is_polling mutex.
  - Uses the same incremental polling logic as the manual endpoint.
  - Advances last_successful_poll_at only after success.

Deployment note:
  If multiple uvicorn workers run, APScheduler fires once per process.
  The is_polling DB mutex prevents duplicate concurrent processing per user.
  For strict single-fire across replicas use APScheduler + PostgreSQL jobstore
  or an external cron (Cloud Scheduler / Render Cron).
"""

import logging
import uuid
import re
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import EmailConnection, Invoice
from app.services.imap_service import imap_service
from app.services.document_context import prepare_classification_context
from app.services.groq_classifier import classify_document, get_unknown_fallback
from app.storage.supabase_storage import storage_service
from app.core.config import settings

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _run_automatic_poll_for_connection(email_conn: EmailConnection) -> None:
    """
    Runs one incremental email poll for a single EmailConnection.
    """
    conn_id = str(email_conn.id)
    user_id_label = str(email_conn.user_id or email_conn.user_id_str or conn_id)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(EmailConnection).where(EmailConnection.id == email_conn.id))
        conn = result.scalar_one_or_none()
        if not conn:
            logger.warning(f"AUTO-POLL: EmailConnection {conn_id} not found.")
            return

        if not conn.is_active or not conn.automatic_polling_enabled:
            logger.info(f"AUTO-POLL: Skipping {conn_id} -- not active or auto-poll disabled.")
            return

        if conn.last_successful_poll_at is None:
            logger.info(f"AUTO-POLL: Skipping {conn_id} -- no successful manual poll yet.")
            return

        if conn.is_polling:
            logger.warning(f"AUTO-POLL: Skipping {conn_id} -- another poll already in progress.")
            return

        poll_upper_bound = datetime.now(timezone.utc)
        since_datetime = conn.last_successful_poll_at

        logger.info(
            f"AUTO-POLL START | conn={conn_id} | user={user_id_label} | "
            f"since={since_datetime.isoformat()} | upper_bound={poll_upper_bound.isoformat()}"
        )

        conn.is_polling = True
        await db.commit()

        poll_successful = False
        try:
            imap_config = {
                "imap_server": conn.imap_host,
                "imap_port": conn.imap_port,
                "email_address": conn.email_address,
                "password": conn.encrypted_password,
            }

            try:
                poll_res = await imap_service.poll_mailbox(
                    imap_config,
                    window_hours=24,
                    since_datetime=since_datetime,
                )
            except Exception as imap_err:
                logger.error(f"AUTO-POLL IMAP FAIL | conn={conn_id} | {imap_err}")
                return

            attachments = poll_res.get("attachments", [])
            logger.info(f"AUTO-POLL | conn={conn_id} | {len(attachments)} attachments fetched")

            hashes = [att["file_hash"] for att in attachments]
            existing_hashes: set = set()
            if hashes:
                from sqlalchemy import or_
                dup_q = select(Invoice).where(Invoice.file_hash.in_(hashes))
                if conn.user_id:
                    dup_q = dup_q.where(
                        or_(Invoice.user_id == conn.user_id, Invoice.user_id.is_(None))
                    )
                dup_res = await db.execute(dup_q)
                existing_hashes = {inv.file_hash for inv in dup_res.scalars().all()}

            unique_candidates = [a for a in attachments if a["file_hash"] not in existing_hashes]
            logger.info(f"AUTO-POLL | conn={conn_id} | {len(unique_candidates)} unique after SHA-256")

            new_documents = 0
            for attachment in unique_candidates:
                try:
                    ctx = prepare_classification_context(attachment)
                    classification_res = classify_document(ctx)
                except Exception as cls_err:
                    logger.error(f"AUTO-POLL classification error for {attachment['filename']}: {cls_err}")
                    classification_res = get_unknown_fallback(f"Classification failure: {cls_err}")

                rel_val = (
                    classification_res.financial_relevance.value
                    if hasattr(classification_res.financial_relevance, "value")
                    else str(classification_res.financial_relevance)
                )
                type_val = (
                    classification_res.document_type.value
                    if hasattr(classification_res.document_type, "value")
                    else str(classification_res.document_type)
                )

                allowed_document_types = {"INVOICE", "CREDIT_NOTE", "DEBIT_NOTE", "UNKNOWN"}
                is_financial_doc = (type_val in allowed_document_types) or (rel_val in ("FINANCIAL", "UNKNOWN"))

                if not is_financial_doc:
                    logger.info(
                        f"AUTO-POLL NON-FINANCIAL DISCARDED | {attachment['filename']} | "
                        f"type={type_val} | relevance={rel_val}"
                    )
                    continue

                invoice_id = uuid.uuid4()
                clean_name = re.sub(r"[^\w\.-]", "_", attachment["filename"])[:100]
                storage_path = f"uploads/{invoice_id}_{clean_name}"
                try:
                    await storage_service.upload_file(
                        file_bytes=attachment["file_bytes"],
                        file_path=storage_path,
                        content_type=attachment["mime_type"],
                    )
                except Exception as upload_err:
                    logger.error(f"AUTO-POLL storage upload fail | {attachment['filename']}: {upload_err}")
                    continue

                tenant_id = "default-tenant-001"
                if conn.user_id:
                    from app.db.models import User
                    user_rec = await db.get(User, conn.user_id)
                    if user_rec:
                        tenant_id = user_rec.tenant_id

                new_invoice = Invoice(
                    id=invoice_id,
                    tenant_id=tenant_id,
                    user_id=conn.user_id,
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
                except Exception as db_err:
                    logger.error(f"AUTO-POLL DB insert fail | {attachment['filename']}: {db_err}")
                    try:
                        await storage_service.delete_file(storage_path)
                    except Exception:
                        pass
                    continue

            conn.last_synced_at = datetime.now(timezone.utc)
            conn.last_successful_poll_at = poll_upper_bound
            conn.is_polling = False
            await db.commit()
            poll_successful = True

            logger.info(
                f"AUTO-POLL COMPLETE | conn={conn_id} | new_documents={new_documents} | "
                f"checkpoint={poll_upper_bound.isoformat()}"
            )

        except Exception as unexpected:
            logger.error(f"AUTO-POLL UNEXPECTED ERROR | conn={conn_id}: {unexpected}", exc_info=True)
        finally:
            if not poll_successful:
                try:
                    conn.is_polling = False
                    await db.commit()
                except Exception as mutex_err:
                    logger.error(f"AUTO-POLL mutex release fail | conn={conn_id}: {mutex_err}")


async def _run_daily_automatic_poll() -> None:
    """Scheduled job: polls all eligible users. Runs at 07:00 UTC every day."""
    logger.info("DAILY AUTO-POLL JOB: Starting...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EmailConnection).where(
                EmailConnection.is_active == True,
                EmailConnection.automatic_polling_enabled == True,
                EmailConnection.last_successful_poll_at.is_not(None),
            )
        )
        connections = result.scalars().all()

    logger.info(f"DAILY AUTO-POLL JOB: Found {len(connections)} eligible connection(s)")

    for conn in connections:
        try:
            await _run_automatic_poll_for_connection(conn)
        except Exception as e:
            logger.error(f"DAILY AUTO-POLL JOB: Unhandled error for conn {conn.id}: {e}", exc_info=True)

    logger.info("DAILY AUTO-POLL JOB: Done.")


def start_scheduler() -> AsyncIOScheduler:
    """Creates and starts the scheduler. Must be called inside a running asyncio event loop."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_daily_automatic_poll,
        trigger=CronTrigger(hour=7, minute=0, timezone="UTC"),
        id="daily_auto_email_poll",
        name="Daily 7AM UTC automatic email poll",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info("Email scheduler started -- daily auto-poll job scheduled for 07:00 UTC.")
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shuts down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Email scheduler stopped.")
