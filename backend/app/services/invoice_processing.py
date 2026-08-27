import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, delete
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice, JournalEntry, JournalLine
from app.storage.supabase_storage import storage_service
from app.services.ai_service import ai_service
from app.services.accounting_service import accounting_service
from app.services.master_data_service import master_data_service
from app.services.journal_generator import journal_generator

logger = logging.getLogger(__name__)


async def process_accounting_only_background(invoice_id: uuid.UUID) -> None:
    """
    Runs ONLY Stage 3 (Qwen3-4B Accounting & Tax reasoning) on an existing invoice
    using its stored Stage 2 extraction and tenant-synced live COA.
    """
    logger.info(f"Starting Stage 3 accounting-only processing for invoice {invoice_id}")

    async with AsyncSessionLocal() as session:
        try:
            query = select(Invoice).where(Invoice.id == invoice_id)
            result = await session.execute(query)
            invoice = result.scalar_one_or_none()

            if not invoice:
                logger.error(f"Invoice {invoice_id} not found.")
                return

            vlm_output = invoice.current_vlm_output or invoice.raw_vlm_output
            if not vlm_output:
                logger.error(f"Invoice {invoice_id} has no VLM extraction data.")
                invoice.accounting_status = "FAILED"
                invoice.error_message = "No extraction data found to categorize."
                await session.commit()
                return

            # Update status to PROCESSING_ACCOUNTING
            invoice.status = "PROCESSING_ACCOUNTING"
            invoice.accounting_status = "PROCESSING_ACCOUNTING"
            invoice.error_message = None
            invoice.updated_at = datetime.now(timezone.utc)
            await session.commit()

            # Prepare invoice JSON for Qwen3-4B
            invoice_payload = vlm_output.get("data") if isinstance(vlm_output, dict) and "data" in vlm_output else vlm_output

            # Fetch active tenant Chart of Accounts & Taxes
            tenant_id = invoice.tenant_id or "default-tenant-001"
            cached_coa = await master_data_service.get_cached_chart_of_accounts(tenant_id, session)
            cached_taxes = await master_data_service.get_cached_taxes(tenant_id, session)

            # Call Qwen3-4B Accounting endpoint on Colab with live COA
            accounting_result = await accounting_service.categorize_accounting(
                invoice_json=invoice_payload,
                chart_of_accounts=cached_coa,
                available_taxes=cached_taxes,
            )

            # Persist complete accounting response (Zero Data Loss)
            invoice.accounting_output = accounting_result
            invoice.current_accounting_output = accounting_result
            invoice.accounting_status = "COMPLETED"
            invoice.status = "COMPLETED"
            invoice.error_message = None
            invoice.updated_at = datetime.now(timezone.utc)

            # Calculate average confidence across line items if available
            line_accounting = accounting_result.get("accounting") or []
            if isinstance(line_accounting, list) and len(line_accounting) > 0:
                confidences = [
                    float(item.get("ai_confidence") or 0.0)
                    for item in line_accounting
                    if isinstance(item, dict) and item.get("ai_confidence") is not None
                ]
                if confidences:
                    invoice.accounting_confidence = round(sum(confidences) / len(confidences), 2)

            # Generate initial balanced draft journal entry (require_approved=False for pre-review drafts)
            journal = journal_generator.generate_journal_entry(
                invoice_data=invoice_payload,
                accounting_data=accounting_result,
                require_approved=False,
            )

            await session.execute(delete(JournalEntry).where(JournalEntry.invoice_id == invoice_id))
            j_entry = JournalEntry(
                invoice_id=invoice_id,
                tenant_id=tenant_id,
                entry_date=journal.get("entry_date"),
                total_debit=journal["total_debit"],
                total_credit=journal["total_credit"],
                is_balanced=journal["is_balanced"],
                status="DRAFT",
            )
            session.add(j_entry)
            await session.flush()

            for item in journal["lines"]:
                line = JournalLine(
                    journal_entry_id=j_entry.id,
                    line_number=item["line_number"],
                    account_id=item.get("account_id"),
                    account_name=item["account_name"],
                    line_type=item["line_type"],
                    amount=item["amount"],
                    description=item.get("description"),
                )
                session.add(line)

            await session.commit()
            logger.info(f"Invoice {invoice_id} Stage 3 accounting categorization completed successfully.")

        except Exception as exc:
            logger.exception(f"Error during Stage 3 accounting for invoice {invoice_id}: {exc}")
            try:
                invoice.accounting_status = "FAILED"
                invoice.status = "FAILED"
                invoice.error_message = str(exc)
                invoice.updated_at = datetime.now(timezone.utc)
                await session.commit()
            except Exception as commit_exc:
                logger.error(f"Failed to record FAILED status for invoice {invoice_id}: {commit_exc}")


async def process_invoice_background(invoice_id: uuid.UUID) -> None:
    """
    Asynchronous background pipeline executing:
    Stage 2: Qwen3-VL Extraction ->
    Stage 3: Qwen3-4B Accounting Classification & TDS Reasoning ->
    Stage 4: Balanced Journal Generation
    """
    logger.info(f"Starting full background processing for invoice {invoice_id}")

    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch invoice record
            query = select(Invoice).where(Invoice.id == invoice_id)
            result = await session.execute(query)
            invoice = result.scalar_one_or_none()

            if not invoice:
                logger.error(f"Invoice {invoice_id} not found in database.")
                return

            tenant_id = invoice.tenant_id or "default-tenant-001"

            # 2. Update status to PROCESSING_VLM (Stage 2)
            invoice.status = "PROCESSING_VLM"
            invoice.accounting_status = "PENDING"
            invoice.error_message = None
            invoice.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Invoice {invoice_id} status updated to PROCESSING_VLM")

            # 3. Retrieve binary from Supabase Storage
            file_bytes = await storage_service.download_file(invoice.file_path)

            # 4. Call Qwen3-VL on Colab
            extraction_result = await ai_service.extract_invoice_vlm(file_bytes)

            # 5. Persist complete raw VLM output & current working output (Zero data loss)
            invoice.raw_vlm_output = extraction_result
            invoice.current_vlm_output = extraction_result
            invoice.status = "PROCESSING_ACCOUNTING"
            invoice.accounting_status = "PROCESSING_ACCOUNTING"
            invoice.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Invoice {invoice_id} Stage 2 VLM complete. Starting Stage 3 Qwen3-4B accounting...")

            # 6. Fetch live tenant Chart of Accounts & Taxes
            cached_coa = await master_data_service.get_cached_chart_of_accounts(tenant_id, session)
            cached_taxes = await master_data_service.get_cached_taxes(tenant_id, session)

            # 7. Call Qwen3-4B Accounting on Colab
            invoice_payload = extraction_result.get("data") if isinstance(extraction_result, dict) and "data" in extraction_result else extraction_result
            accounting_result = await accounting_service.categorize_accounting(
                invoice_json=invoice_payload,
                chart_of_accounts=cached_coa,
                available_taxes=cached_taxes,
            )

            # 8. Persist complete accounting response
            invoice.accounting_output = accounting_result
            invoice.current_accounting_output = accounting_result
            invoice.accounting_status = "COMPLETED"
            invoice.status = "COMPLETED"
            invoice.error_message = None
            invoice.updated_at = datetime.now(timezone.utc)

            line_accounting = accounting_result.get("accounting") or []
            if isinstance(line_accounting, list) and len(line_accounting) > 0:
                confidences = [
                    float(item.get("ai_confidence") or 0.0)
                    for item in line_accounting
                    if isinstance(item, dict) and item.get("ai_confidence") is not None
                ]
                if confidences:
                    invoice.accounting_confidence = round(sum(confidences) / len(confidences), 2)

            # 9. Generate balanced draft journal entry (require_approved=False for pre-review drafts)
            journal = journal_generator.generate_journal_entry(
                invoice_data=invoice_payload,
                accounting_data=accounting_result,
                require_approved=False,
            )

            await session.execute(delete(JournalEntry).where(JournalEntry.invoice_id == invoice_id))
            j_entry = JournalEntry(
                invoice_id=invoice_id,
                tenant_id=tenant_id,
                entry_date=journal.get("entry_date"),
                total_debit=journal["total_debit"],
                total_credit=journal["total_credit"],
                is_balanced=journal["is_balanced"],
                status="DRAFT",
            )
            session.add(j_entry)
            await session.flush()

            for item in journal["lines"]:
                line = JournalLine(
                    journal_entry_id=j_entry.id,
                    line_number=item["line_number"],
                    account_id=item.get("account_id"),
                    account_name=item["account_name"],
                    line_type=item["line_type"],
                    amount=item["amount"],
                    description=item.get("description"),
                )
                session.add(line)

            await session.commit()
            logger.info(f"Invoice {invoice_id} full Stage 2 + Stage 3 processing completed successfully.")

        except Exception as exc:
            logger.exception(f"Error processing invoice {invoice_id}: {exc}")
            try:
                invoice.status = "FAILED"
                invoice.error_message = str(exc)
                invoice.updated_at = datetime.now(timezone.utc)
                await session.commit()
            except Exception as commit_exc:
                logger.error(f"Failed to record FAILED status for invoice {invoice_id}: {commit_exc}")
