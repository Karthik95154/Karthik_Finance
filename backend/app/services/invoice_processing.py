import logging
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, delete
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice, JournalEntry, JournalLine
from app.storage.supabase_storage import storage_service
from app.services.ai_service import ai_service
from app.services.accounting_service import accounting_service
from app.services.gst_engine import gst_engine
from app.services.itc_engine import itc_engine
from app.services.financial_validator import financial_validator
from app.services.journal_generator import journal_generator, sync_relational_journal
from app.services.master_data_service import master_data_service

logger = logging.getLogger(__name__)


def get_effective_invoice_data(invoice: Invoice) -> dict:
    """
    Returns complete invoice JSON data for Stage 3 & Stage 4, ensuring base VLM extraction
    fields (line items, totals, vendor/customer, taxes) are fully preserved even if
    current_vlm_output was partially edited.
    """
    raw = invoice.raw_vlm_output or {}
    raw_data = raw.get("data") if isinstance(raw, dict) and "data" in raw else raw
    if not isinstance(raw_data, dict):
        raw_data = {}

    curr = invoice.current_vlm_output or {}
    curr_data = curr.get("data") if isinstance(curr, dict) and "data" in curr else curr
    if not isinstance(curr_data, dict):
        curr_data = {}

    # Merge base raw_data with user edits from curr_data
    merged = dict(raw_data)
    for k, v in curr_data.items():
        if v is not None:
            if k == "line_items" and isinstance(v, list) and len(v) == 0 and raw_data.get("line_items"):
                continue
            merged[k] = v

    return merged


async def process_accounting_only_background(invoice_id: uuid.UUID) -> None:
    """
    Runs Stage 3 (Qwen3-4B Accounting & Tax reasoning) and Stage 4-6 (Deterministic GST, ITC,
    Financial Validator & Journal Generator) on an existing invoice using its stored extraction.
    DOES NOT call Qwen3-VL again.
    """
    logger.info(f"Starting Stage 3, 4, 5 & 6 processing for invoice {invoice_id}")

    async with AsyncSessionLocal() as session:
        try:
            query = select(Invoice).where(Invoice.id == invoice_id)
            result = await session.execute(query)
            invoice = result.scalar_one_or_none()

            if not invoice:
                logger.error(f"Invoice {invoice_id} not found.")
                return

            if not invoice.raw_vlm_output and not invoice.current_vlm_output:
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

            # Prepare complete effective invoice JSON for Qwen3-4B and GST/ITC
            invoice_payload = get_effective_invoice_data(invoice)
            tenant_id = invoice.tenant_id or "default-tenant-001"
            cached_coa = await master_data_service.get_cached_chart_of_accounts(tenant_id, session)
            cached_taxes = await master_data_service.get_cached_taxes(tenant_id, session)

            # 1. Call Qwen3-4B Accounting endpoint
            accounting_result = await accounting_service.categorize_accounting(
                invoice_json=invoice_payload,
                chart_of_accounts=cached_coa,
                available_taxes=cached_taxes,
            )

            # 2. Call Deterministic Stage 4 GST Engine
            gst_result = gst_engine.evaluate_gst(invoice_payload)

            # 3. Call Deterministic Stage 4 ITC Engine
            itc_result = itc_engine.evaluate_itc(invoice_payload, accounting_result)

            # 4. Call Deterministic Stage 5 Financial Validator
            financial_validation_result = financial_validator.validate_invoice(invoice_payload, gst_result)

            # 5. Call Deterministic Stage 6 Journal Generator (Double-Entry General Ledger Preview)
            journal_result = journal_generator.generate_journal(
                invoice_data=invoice_payload,
                accounting_classification=accounting_result,
                gst_result=gst_result,
                itc_result=itc_result,
                tds_result=accounting_result.get("tds") if accounting_result else None,
                financial_validation_result=financial_validation_result,
            )

            # Persist results (Zero Data Loss)
            invoice.accounting_output = accounting_result
            invoice.current_accounting_output = accounting_result
            invoice.gst_result = gst_result
            invoice.itc_result = itc_result
            invoice.financial_validation_result = financial_validation_result
            invoice.journal_entry = journal_result
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

            await sync_relational_journal(session, invoice.id, journal_result)
            await session.commit()
            logger.info(f"Invoice {invoice_id} Stage 3, 4, 5 & 6 processing completed successfully.")

        except Exception as exc:
            logger.exception(f"Error during Stage 3, 4, 5 & 6 processing for invoice {invoice_id}: {exc}")
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
    Stage 4: Deterministic GST & ITC Engine ->
    Stage 5: Deterministic Financial Validation / Reconciliation ->
    Stage 6: Deterministic Balanced Journal Generation Preview
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

            # 8. Call Deterministic Stage 4 GST Engine
            gst_result = gst_engine.evaluate_gst(invoice_payload)

            # 9. Call Deterministic Stage 4 ITC Engine
            itc_result = itc_engine.evaluate_itc(invoice_payload, accounting_result)

            # 10. Call Deterministic Stage 5 Financial Validator
            financial_validation_result = financial_validator.validate_invoice(invoice_payload, gst_result)

            # 11. Call Deterministic Stage 6 Journal Generator
            journal_result = journal_generator.generate_journal(
                invoice_data=invoice_payload,
                accounting_classification=accounting_result,
                gst_result=gst_result,
                itc_result=itc_result,
                tds_result=accounting_result.get("tds") if accounting_result else None,
                financial_validation_result=financial_validation_result,
            )

            # 12. Persist complete accounting, GST/ITC, financial validation, and journal responses
            invoice.accounting_output = accounting_result
            invoice.current_accounting_output = accounting_result
            invoice.gst_result = gst_result
            invoice.itc_result = itc_result
            invoice.financial_validation_result = financial_validation_result
            invoice.journal_entry = journal_result
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

            await sync_relational_journal(session, invoice.id, journal_result)
            await session.commit()
            logger.info(f"Invoice {invoice_id} full Stage 2, 3, 4, 5 & 6 processing completed successfully.")

        except Exception as exc:
            logger.exception(f"Error processing invoice {invoice_id}: {exc}")
            try:
                invoice.status = "FAILED"
                invoice.error_message = str(exc)
                invoice.updated_at = datetime.now(timezone.utc)
                await session.commit()
            except Exception as commit_exc:
                logger.error(f"Failed to record FAILED status for invoice {invoice_id}: {commit_exc}")
