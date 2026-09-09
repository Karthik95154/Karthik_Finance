import logging
import uuid
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select, delete
from app.db.database import AsyncSessionLocal
from app.db.models import Invoice, JournalEntry, JournalLine
from app.storage.supabase_storage import storage_service
from app.services.ai_service import ai_service
from app.services.accounting_service import accounting_service
from app.services.tds_service import tds_service
from app.services.tds_engine import tds_engine
from app.services.gst_engine import gst_engine
from app.services.itc_engine import itc_engine
from app.services.financial_validator import financial_validator
from app.services.journal_generator import journal_generator, sync_relational_journal
from app.services.master_data_service import master_data_service

logger = logging.getLogger(__name__)


def get_effective_invoice_data(invoice: Invoice) -> dict:
    """
    Returns complete invoice JSON data for Stage 3 & Stage 4, ensuring base VLM extraction
    fields (line items, totals, vendor/customer, taxes, raw_fields) are fully resolved and preserved.
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

    # Fallback to raw_fields if top-level fields were cleared by post-processing
    raw_f = raw_data.get("raw_fields") if isinstance(raw_data, dict) and raw_data.get("raw_fields") else (raw.get("raw_fields") if isinstance(raw, dict) else {})
    if isinstance(raw_f, dict):
        if not merged.get("vendor_gstin") and raw_f.get("vendor_gstin"):
            merged["vendor_gstin"] = raw_f.get("vendor_gstin")
        if not merged.get("vendor_pan") and raw_f.get("vendor_pan"):
            merged["vendor_pan"] = raw_f.get("vendor_pan")
        elif not merged.get("vendor_pan") and merged.get("vendor_gstin") and len(str(merged.get("vendor_gstin"))) == 15:
            merged["vendor_pan"] = str(merged.get("vendor_gstin"))[2:12]

        if not merged.get("customer_gstin") and raw_f.get("customer_gstin"):
            merged["customer_gstin"] = raw_f.get("customer_gstin")
        if not merged.get("customer_pan") and raw_f.get("customer_pan"):
            merged["customer_pan"] = raw_f.get("customer_pan")
        elif not merged.get("customer_pan") and merged.get("customer_gstin") and len(str(merged.get("customer_gstin"))) == 15:
            merged["customer_pan"] = str(merged.get("customer_gstin"))[2:12]

        if not merged.get("invoice_number") and raw_f.get("invoice_number"):
            merged["invoice_number"] = raw_f.get("invoice_number")
        if not merged.get("vendor_name") and raw_f.get("vendor_name"):
            merged["vendor_name"] = raw_f.get("vendor_name")
        if not merged.get("customer_name") and raw_f.get("customer_name"):
            merged["customer_name"] = raw_f.get("customer_name")
        if not merged.get("payment_terms") and raw_f.get("payment_terms"):
            merged["payment_terms"] = raw_f.get("payment_terms")
        if not merged.get("vendor_address") and raw_f.get("vendor_address"):
            merged["vendor_address"] = raw_f.get("vendor_address")
        if not merged.get("customer_address") and raw_f.get("customer_address"):
            merged["customer_address"] = raw_f.get("customer_address")
        if not merged.get("vendor_phone") and raw_f.get("vendor_phone"):
            merged["vendor_phone"] = raw_f.get("vendor_phone")
        if not merged.get("vendor_email") and raw_f.get("vendor_email"):
            merged["vendor_email"] = raw_f.get("vendor_email")
        if not merged.get("place_of_supply") and raw_f.get("place_of_supply"):
            merged["place_of_supply"] = raw_f.get("place_of_supply")

    # Resolve line items from raw_fields if needed
    items = merged.get("line_items") or []
    resolved_items = []
    for idx, item in enumerate(items, 1):
        it = dict(item) if isinstance(item, dict) else {}
        it_rf = it.get("raw_fields") or {}
        if isinstance(it_rf, dict):
            if not it.get("hsn_code") and it_rf.get("hsn_code"):
                it["hsn_code"] = it_rf.get("hsn_code")
            if not it.get("description") and it_rf.get("description"):
                it["description"] = it_rf.get("description")
            if (it.get("quantity") is None) and it_rf.get("quantity"):
                try:
                    it["quantity"] = float(str(it_rf.get("quantity")).replace(",", ""))
                except Exception:
                    pass
            if (it.get("unit_price") is None) and it_rf.get("unit_price"):
                try:
                    it["unit_price"] = float(str(it_rf.get("unit_price")).replace(",", ""))
                except Exception:
                    pass
            if (it.get("taxable_amount") is None) and it_rf.get("taxable_amount"):
                try:
                    it["taxable_amount"] = float(str(it_rf.get("taxable_amount")).replace(",", ""))
                except Exception:
                    pass
            if (it.get("discount") is None) and it_rf.get("discount") is not None:
                it["discount"] = it_rf.get("discount")
            if (it.get("discount_type") is None) and it_rf.get("discount_type"):
                it["discount_type"] = it_rf.get("discount_type")

            if (it.get("cgst_amount") is None) and it_rf.get("cgst_amount") is not None:
                try:
                    it["cgst_amount"] = float(str(it_rf.get("cgst_amount")).replace(",", ""))
                except Exception:
                    pass
            if (it.get("sgst_amount") is None) and it_rf.get("sgst_amount") is not None:
                try:
                    it["sgst_amount"] = float(str(it_rf.get("sgst_amount")).replace(",", ""))
                except Exception:
                    pass
            if (it.get("igst_amount") is None) and it_rf.get("igst_amount") is not None:
                try:
                    it["igst_amount"] = float(str(it_rf.get("igst_amount")).replace(",", ""))
                except Exception:
                    pass
            if (it.get("cess_amount") is None) and it_rf.get("cess_amount") is not None:
                try:
                    it["cess_amount"] = float(str(it_rf.get("cess_amount")).replace(",", ""))
                except Exception:
                    pass

        # Fallback to hsn_sac_code if canonical hsn_code is missing
        if not it.get("hsn_code") and it.get("hsn_sac_code"):
            it["hsn_code"] = str(it.get("hsn_sac_code")).strip()

        # Deterministically resolve discount semantics for line item
        from app.services.financial_validator import parse_discount_semantics
        disc_val, disc_type, _ = parse_discount_semantics(it)
        if disc_val is not None:
            it["discount"] = disc_val
            if disc_type:
                it["discount_type"] = disc_type

        # If taxable_amount is missing, derive from quantity * unit_price - discount, or fallback to line_amount - discount
        if it.get("taxable_amount") is None:
            if it.get("quantity") is not None and it.get("unit_price") is not None:
                gross = float(it["quantity"]) * float(it["unit_price"])
                d_amt = 0.0
                if it.get("discount") is not None:
                    d_val = float(it["discount"])
                    if it.get("discount_type") == "percentage":
                        d_amt = gross * d_val / 100.0
                    else:
                        d_amt = d_val
                it["taxable_amount"] = round(gross - d_amt, 2)
            elif it.get("line_amount") is not None:
                # Safe fallback: generic line_amount minus discount if no qty/unit_price
                l_amt = float(it["line_amount"])
                d_amt = 0.0
                if it.get("discount") is not None:
                    d_val = float(it["discount"])
                    if it.get("discount_type") == "percentage":
                        d_amt = l_amt * d_val / 100.0
                    else:
                        d_amt = d_val
                it["taxable_amount"] = round(l_amt - d_amt, 2)

        # Reconcile line item total = taxable_amount + applicable taxes
        if it.get("taxable_amount") is not None:
            taxable_val = float(it["taxable_amount"])
            line_taxes = 0.0
            for tax_k in ["cgst_amount", "sgst_amount", "igst_amount", "cess_amount"]:
                if it.get(tax_k) is not None:
                    line_taxes += float(it[tax_k])
            calc_line_tot = round(taxable_val + line_taxes, 2)
            cur_tot = float(it["total"]) if it.get("total") is not None else None
            if cur_tot is None:
                it["total"] = calc_line_tot
            elif line_taxes > 0 and (abs(cur_tot - taxable_val) < 0.05 or abs(cur_tot - calc_line_tot) > 0.05):
                it["total"] = calc_line_tot

        resolved_items.append(it)
    merged["line_items"] = resolved_items

    # Normalize dates according to Indian & International date standards
    from app.core.date_utils import parse_and_normalize_date
    if merged.get("invoice_date"):
        merged["invoice_date"] = parse_and_normalize_date(merged["invoice_date"])
    if merged.get("due_date"):
        merged["due_date"] = parse_and_normalize_date(merged["due_date"])

    return merged


async def process_accounting_only_background(invoice_id: uuid.UUID) -> None:
    """
    Runs downstream Stage 3-6 (COA mapping, TDS, GST, ITC, Financial Validator & Journal Generator)
    on an existing invoice using its stored extraction. Does not re-call Kimi K3 AI inference.
    """
    logger.info(f"Starting Stage 3, 4, 5 & 6 processing for invoice {invoice_id}")

    invoice_payload = None
    cached_coa = None
    cached_taxes = None

    # Step 1: Initial state transition and load cached master data in a short-lived session
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

            # Prepare complete single effective invoice JSON for COA, TDS, GST/ITC
            invoice_payload = get_effective_invoice_data(invoice)
            tenant_id = invoice.tenant_id or "default-tenant-001"
            normalized_accounting_state = invoice.current_accounting_output or invoice.accounting_output
            cached_coa = await master_data_service.get_cached_chart_of_accounts(tenant_id, session)
            cached_taxes = await master_data_service.get_cached_taxes(tenant_id, session)
        except Exception as exc:
            logger.exception(f"Error initializing Stage 3 processing for invoice {invoice_id}: {exc}")
            try:
                res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
                inv = res.scalar_one_or_none()
                if inv:
                    inv.accounting_status = "FAILED"
                    inv.status = "FAILED"
                    inv.error_message = str(exc)
                    inv.updated_at = datetime.now(timezone.utc)
                    await session.commit()
            except Exception:
                pass
            return

    # Step 2: External AI Inference & Deterministic Computations (Zero DB connections held)
    try:
        # Check if we already have authoritative VLM accounting classification from Stage 1/2
        coa_lines = []
        if isinstance(normalized_accounting_state, dict) and isinstance(normalized_accounting_state.get("accounting"), list) and normalized_accounting_state["accounting"]:
            coa_lines = normalized_accounting_state["accounting"]
            logger.info(f"[STAGE-3] Preserving {len(coa_lines)} authoritative COA classification(s) from VLM adapter.")
            tds_res = await tds_service.assess_tds(invoice_json=invoice_payload)
        else:
            # 1. Call COA and TDS services concurrently using the EXACT SAME invoice_payload
            coa_task = accounting_service.categorize_accounting(
                invoice_json=invoice_payload,
                chart_of_accounts=cached_coa,
                available_taxes=cached_taxes,
            )
            tds_task = tds_service.assess_tds(
                invoice_json=invoice_payload,
            )

            coa_res, tds_res = await asyncio.gather(coa_task, tds_task, return_exceptions=True)

            if isinstance(coa_res, dict):
                coa_lines = coa_res.get("accounting") or []
            elif isinstance(coa_res, Exception):
                logger.warning(f"COA service exception for invoice {invoice_id}: {coa_res}")
                coa_lines = accounting_service._build_unavailable_response(invoice_payload, str(coa_res)).get("accounting", [])

        accounting_lines = coa_lines

        tds_assessment = {}
        if isinstance(tds_res, dict):
            tds_assessment = tds_res.get("tds_assessment") or {}
        elif isinstance(tds_res, Exception):
            logger.warning(f"TDS service exception for invoice {invoice_id}: {tds_res}")
            tds_assessment = tds_service._build_unavailable_response(str(tds_res)).get("tds_assessment", {})

        # 2. Call Deterministic Stage 4 GST Engine
        gst_result = gst_engine.evaluate_gst(invoice_payload)

        # 3. Call Deterministic Stage 4 ITC Engine via SSOT
        from app.services.itc_engine import get_effective_itc_data
        combined_accounting_context = {
            "accounting": accounting_lines,
            "tds_assessment": tds_assessment,
        }
        itc_result = get_effective_itc_data(
            invoice_or_data=invoice_payload,
            accounting_output=combined_accounting_context,
        )

        # 4. Call Deterministic Stage 5 Financial Validator
        financial_validation_result = financial_validator.validate_invoice(invoice_payload, gst_result)

        # 5. Deterministic Final TDS (Authoritative statutory calculation on resolved base amount)
        from app.services.tds_engine import get_effective_tds_data
        effective_tds = get_effective_tds_data({"tds_assessment": tds_assessment})
        tds_applicable = bool(effective_tds.get("applicable"))

        tds_base_amt = tds_engine.determine_tds_base_amount(invoice_payload, effective_tds)
        tds_rate = effective_tds.get("rate")
        tds_section = effective_tds.get("section")
        tds_provision = effective_tds.get("provision")
        tds_nature = effective_tds.get("nature_of_payment")
        vendor_pan = invoice_payload.get("vendor_pan")

        final_tds_calc = tds_engine.calculate_tds(
            applicable=tds_applicable,
            section=tds_section,
            provision=tds_provision,
            nature_of_payment=tds_nature,
            base_amount=tds_base_amt,
            rate=float(tds_rate) if tds_rate is not None else None,
            vendor_pan=vendor_pan,
        )

        # Build unified accounting output maintaining clear proposal vs final separation
        persisted_accounting_output = {
            "accounting": accounting_lines,
            "tds_assessment": {
                **tds_assessment,
                "applicable": tds_applicable,
                "tds_applicable": tds_applicable,
                "section": tds_section,
                "tds_section": tds_section,
                "provision": tds_provision,
                "tds_provision": tds_provision,
                "nature_of_payment": tds_nature,
                "tds_rate": final_tds_calc.get("rate") if tds_applicable else None,
                "rate": final_tds_calc.get("rate") if tds_applicable else None,
                "approved_tds_rate": final_tds_calc.get("rate") if tds_applicable else None,
                "tds_base_amount": final_tds_calc.get("base_amount") if tds_applicable else None,
                "base_amount": final_tds_calc.get("base_amount") if tds_applicable else None,
                "proposed_tds_amount": final_tds_calc.get("tds_amount") if tds_applicable else None,
                "tds_amount": final_tds_calc.get("tds_amount") if tds_applicable else None,
                "tds_reasoning": final_tds_calc.get("reason"),
            },
            "tds_final": final_tds_calc,
            "tds": final_tds_calc,
            "itc_assessment": itc_result,
        }

        # 6. Call Deterministic Stage 6 Journal Generator (Double-Entry General Ledger Preview)
        journal_result = journal_generator.generate_journal(
            invoice_data=invoice_payload,
            accounting_classification=persisted_accounting_output,
            gst_result=gst_result,
            itc_result=itc_result,
            tds_result=final_tds_calc,
            financial_validation_result=financial_validation_result,
        )

        avg_confidence = None
        if isinstance(accounting_lines, list) and len(accounting_lines) > 0:
            confidences = [
                float(item.get("confidence_score") if item.get("confidence_score") is not None else (item.get("ai_confidence") or 0.0))
                for item in accounting_lines
                if isinstance(item, dict) and (item.get("confidence_score") is not None or item.get("ai_confidence") is not None)
            ]
            if confidences:
                avg_confidence = round(sum(confidences) / len(confidences), 2)

    except Exception as exc:
        logger.exception(f"Error during AI/rule computation for invoice {invoice_id}: {exc}")
        async with AsyncSessionLocal() as session:
            try:
                res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
                inv = res.scalar_one_or_none()
                if inv:
                    inv.accounting_status = "FAILED"
                    inv.status = "FAILED"
                    inv.error_message = str(exc)
                    inv.updated_at = datetime.now(timezone.utc)
                    await session.commit()
            except Exception as commit_exc:
                logger.error(f"Failed to record FAILED status for invoice {invoice_id}: {commit_exc}")
        return

    # Step 3: Persist results in a fresh short-lived session
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
            invoice = res.scalar_one_or_none()
            if not invoice:
                logger.error(f"Invoice {invoice_id} not found during result persistence.")
                return

            invoice.accounting_output = persisted_accounting_output
            invoice.current_accounting_output = persisted_accounting_output
            invoice.gst_result = gst_result
            invoice.itc_result = itc_result
            invoice.financial_validation_result = financial_validation_result
            invoice.journal_entry = journal_result
            invoice.accounting_status = "COMPLETED"
            invoice.status = "COMPLETED"
            invoice.error_message = None
            invoice.updated_at = datetime.now(timezone.utc)
            if avg_confidence is not None:
                invoice.accounting_confidence = avg_confidence

            await sync_relational_journal(session, invoice.id, journal_result)
            await session.commit()
            logger.info(f"Invoice {invoice_id} Stage 3, 4, 5 & 6 processing completed successfully.")
        except Exception as exc:
            logger.exception(f"Error persisting Stage 3-6 results for invoice {invoice_id}: {exc}")
            try:
                res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
                inv = res.scalar_one_or_none()
                if inv:
                    inv.accounting_status = "FAILED"
                    inv.status = "FAILED"
                    inv.error_message = str(exc)
                    inv.updated_at = datetime.now(timezone.utc)
                    await session.commit()
            except Exception as commit_exc:
                logger.error(f"Failed to record FAILED status for invoice {invoice_id}: {commit_exc}")


async def process_invoice_background(invoice_id: uuid.UUID) -> None:
    """
    Asynchronous background pipeline executing:
    Stage 1: OpenAI Vision Extraction + Line Item COA + TDS Proposal ->
    Stage 2: ModelResponseAdapter Normalization & Per-Line Zoho COA Verification ->
    Stage 3: Deterministic Statutory TDS Calculation ->
    Stage 4: Deterministic GST & ITC Engine ->
    Stage 5: Deterministic Financial Validation / Reconciliation ->
    Stage 6: Deterministic Balanced Journal Generation Preview
    """
    logger.info(f"Starting full background processing for invoice {invoice_id}")

    tenant_id = "default-tenant-001"
    user_id = None
    file_path = None
    file_name = None
    file_mime_type = None
    cached_coa = []

    # 1. Retrieve invoice, user context, and user's active Zoho COA in a short-lived session
    async with AsyncSessionLocal() as session:
        try:
            query = select(Invoice).where(Invoice.id == invoice_id)
            result = await session.execute(query)
            invoice = result.scalar_one_or_none()

            if not invoice:
                logger.error(f"Invoice {invoice_id} not found in database.")
                return

            tenant_id = invoice.tenant_id or "default-tenant-001"
            user_id = invoice.user_id
            file_path = invoice.file_path
            file_name = invoice.file_name
            file_mime_type = invoice.mime_type or "application/pdf"

            invoice.status = "PROCESSING_VLM"
            invoice.accounting_status = "PENDING"
            invoice.error_message = None
            invoice.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Invoice {invoice_id} status updated to PROCESSING_VLM")

            # Retrieve active Zoho Chart of Accounts strictly scoped to tenant_id & organization
            try:
                cached_coa = await master_data_service.get_cached_chart_of_accounts(
                    tenant_id=tenant_id,
                    db=session,
                )
            except Exception as coa_exc:
                logger.warning(f"Could not fetch Zoho COA for tenant {tenant_id}: {coa_exc}")
                cached_coa = []
        except Exception as exc:
            logger.exception(f"Error marking invoice {invoice_id} as PROCESSING_VLM: {exc}")
            return

    # 2. Retrieve binary from Supabase Storage (no DB connection held)
    try:
        file_bytes = await storage_service.download_file(file_path)
    except Exception as exc:
        logger.exception(f"Error downloading file for invoice {invoice_id}: {exc}")
        async with AsyncSessionLocal() as session:
            try:
                res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
                inv = res.scalar_one_or_none()
                if inv:
                    inv.status = "FAILED"
                    inv.error_message = f"Failed to download invoice file: {str(exc)}"
                    inv.updated_at = datetime.now(timezone.utc)
                    await session.commit()
            except Exception:
                pass
        return

    # 3. Call OpenAI Vision Intelligence with Base64 image & user's Zoho COA
    raw_model_response = None
    try:
        raw_model_response = await ai_service.extract_invoice_vlm(
            file_bytes=file_bytes,
            filename=file_name or "invoice.pdf",
            content_type=file_mime_type,
            chart_of_accounts=cached_coa,
        )
    except Exception as vlm_err:
        err_msg = f"Extraction service unavailable / failed: {str(vlm_err)}"
        logger.warning(
            f"Invoice {invoice_id} extraction failed (AI service unavailable). Setting status to NOT_PROCESSED. Reason: {err_msg}"
        )

        async with AsyncSessionLocal() as session:
            try:
                res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
                inv = res.scalar_one_or_none()
                if inv:
                    inv.status = "NOT_PROCESSED"
                    inv.accounting_status = "NOT_PROCESSED"
                    inv.error_message = f"[EXTRACTION_UNAVAILABLE] {err_msg}"
                    inv.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    logger.info(f"Invoice {invoice_id} set to NOT_PROCESSED due to AI service unavailability.")
            except Exception as commit_err:
                logger.error(f"Failed to update status to NOT_PROCESSED for invoice {invoice_id}: {commit_err}")
        return

    # 4. Normalize model response via ModelResponseAdapter
    from app.services.model_response_adapter import ModelResponseAdapter
    normalized = ModelResponseAdapter.normalize_model_response(
        model_response=raw_model_response,
        user_zoho_coa=cached_coa,
    )

    raw_snapshot = normalized["raw_vlm_output"]
    norm_vlm_dict = {"data": normalized["normalized_data"]}
    norm_accounting_dict = normalized["normalized_accounting"]

    # Calculate Indian Accounting Period category based on normalized invoice_date
    from app.core.date_utils import calculate_invoice_accounting_period
    period_category = None
    period_decision = "NOT_REQUIRED"
    inv_d_val = normalized["normalized_data"].get("invoice_date")
    if inv_d_val:
        period_category, _, _ = calculate_invoice_accounting_period(inv_d_val)
        if period_category == "PREVIOUS_FINANCIAL_YEAR":
            period_decision = "PENDING"

    # 5. Persist extraction result & initial normalized outputs in database
    async with AsyncSessionLocal() as session:
        try:
            query = select(Invoice).where(Invoice.id == invoice_id)
            result = await session.execute(query)
            invoice = result.scalar_one_or_none()
            if invoice:
                invoice.raw_vlm_output = raw_snapshot
                invoice.current_vlm_output = norm_vlm_dict
                invoice.accounting_output = norm_accounting_dict
                invoice.current_accounting_output = norm_accounting_dict
                invoice.status = "PROCESSING_ACCOUNTING"
                invoice.period_category = period_category
                invoice.period_decision = period_decision
                invoice.updated_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info(f"Invoice {invoice_id} extraction complete (period: {period_category}). Executing downstream deterministic engines...")
        except Exception as exc:
            logger.exception(f"Error persisting extraction result for invoice {invoice_id}: {exc}")
            try:
                res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
                inv = res.scalar_one_or_none()
                if inv:
                    inv.status = "FAILED"
                    inv.error_message = str(exc)
                    inv.updated_at = datetime.now(timezone.utc)
                    await session.commit()
            except Exception as commit_exc:
                logger.error(f"Failed to record FAILED status for invoice {invoice_id}: {commit_exc}")
            return

    # 6. Execute downstream Stage 3-6 Deterministic Engines (GST, ITC, Financial Validator, Journal Generator)
    await process_accounting_downstream_background(invoice_id)


async def process_accounting_downstream_background(invoice_id) -> None:
    logger.info(f"Starting downstream accounting processing for approved HITL invoice {invoice_id}")
    tenant_id = None
    extraction_result = None
    cached_coa = None
    cached_taxes = None

    # Step 1: Read invoice state and cached master data in a short-lived session
    async with AsyncSessionLocal() as session:
        try:
            query = select(Invoice).where(Invoice.id == invoice_id)
            result = await session.execute(query)
            invoice = result.scalar_one_or_none()

            if not invoice:
                logger.error(f"Invoice {invoice_id} not found.")
                return

            tenant_id = invoice.tenant_id or "default-tenant-001"
            extraction_result = invoice.current_vlm_output
            normalized_accounting_state = invoice.current_accounting_output or invoice.accounting_output

            # Fetch live tenant Chart of Accounts & Taxes
            cached_coa = await master_data_service.get_cached_chart_of_accounts(tenant_id, session)
            cached_taxes = await master_data_service.get_cached_taxes(tenant_id, session)
        except Exception as exc:
            logger.exception(f"Error reading invoice {invoice_id} for downstream processing: {exc}")
            try:
                res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
                inv = res.scalar_one_or_none()
                if inv:
                    inv.status = "FAILED"
                    inv.error_message = str(exc)
                    inv.updated_at = datetime.now(timezone.utc)
                    await session.commit()
            except Exception:
                pass
            return

    # Step 2: External AI Inference & Deterministic Computations (Zero DB connections held)
    try:
        invoice_payload = extraction_result.get("data") if isinstance(extraction_result, dict) and "data" in extraction_result else extraction_result

        coa_lines = []
        if isinstance(normalized_accounting_state, dict) and isinstance(normalized_accounting_state.get("accounting"), list) and normalized_accounting_state["accounting"]:
            coa_lines = normalized_accounting_state["accounting"]
            logger.info(f"[DOWNSTREAM] Preserving {len(coa_lines)} authoritative COA classification(s) from VLM intelligence adapter.")
        else:
            coa_res = await accounting_service.categorize_accounting(
                invoice_json=invoice_payload,
                chart_of_accounts=cached_coa,
                available_taxes=cached_taxes,
            )
            if isinstance(coa_res, dict):
                coa_lines = coa_res.get("accounting") or []

        raw_vlm_output = invoice.raw_vlm_output or {}
        tds_payload = {
            **invoice_payload,
            "raw_vlm_output": raw_vlm_output,
            "tds_support": raw_vlm_output.get("tds_support"),
        }
        if isinstance(normalized_accounting_state, dict) and isinstance(normalized_accounting_state.get("tds_assessment"), dict):
            tds_payload["tds_assessment"] = normalized_accounting_state["tds_assessment"]

        tds_task = tds_service.assess_tds(
            invoice_json=tds_payload,
        )

        tds_res = await tds_task

        accounting_lines = coa_lines

        tds_assessment = {}
        if isinstance(tds_res, dict):
            tds_assessment = tds_res.get("tds_assessment") or {}
        elif isinstance(tds_res, Exception):
            logger.warning(f"TDS service error for invoice {invoice_id}: {tds_res}")
            tds_assessment = tds_service._build_unavailable_response(str(tds_res)).get("tds_assessment", {})

        # Deterministic Stage 4 GST Engine
        gst_result = gst_engine.evaluate_gst(invoice_payload)

        # Deterministic Stage 4 ITC Engine via SSOT
        from app.services.itc_engine import get_effective_itc_data
        combined_accounting_context = {
            "accounting": accounting_lines,
            "tds_assessment": tds_assessment,
        }
        itc_result = get_effective_itc_data(
            invoice_or_data=invoice_payload,
            accounting_output=combined_accounting_context,
        )

        # Deterministic Stage 5 Financial Validator
        financial_validation_result = financial_validator.validate_invoice(invoice_payload, gst_result)

        # Deterministic Final TDS (Authoritative statutory calculation on resolved base amount)
        from app.services.tds_engine import get_effective_tds_data
        effective_tds = get_effective_tds_data({"tds_assessment": tds_assessment})
        tds_applicable = bool(effective_tds.get("applicable"))

        tds_base_amt = tds_engine.determine_tds_base_amount(invoice_payload, effective_tds)
        tds_rate = effective_tds.get("rate")
        tds_section = effective_tds.get("section")
        tds_provision = effective_tds.get("provision")
        tds_nature = effective_tds.get("nature_of_payment")
        vendor_pan = invoice_payload.get("vendor_pan")

        final_tds_calc = tds_engine.calculate_tds(
            applicable=tds_applicable,
            section=tds_section,
            provision=tds_provision,
            nature_of_payment=tds_nature,
            base_amount=tds_base_amt,
            rate=float(tds_rate) if tds_rate is not None else None,
            vendor_pan=vendor_pan,
        )

        persisted_accounting_output = {
            "accounting": accounting_lines,
            "tds_assessment": {
                **tds_assessment,
                "applicable": tds_applicable,
                "tds_applicable": tds_applicable,
                "section": tds_section,
                "tds_section": tds_section,
                "provision": tds_provision,
                "tds_provision": tds_provision,
                "nature_of_payment": tds_nature,
                "tds_rate": final_tds_calc.get("rate") if tds_applicable else None,
                "rate": final_tds_calc.get("rate") if tds_applicable else None,
                "approved_tds_rate": final_tds_calc.get("rate") if tds_applicable else None,
                "tds_base_amount": final_tds_calc.get("base_amount") if tds_applicable else None,
                "base_amount": final_tds_calc.get("base_amount") if tds_applicable else None,
                "proposed_tds_amount": final_tds_calc.get("tds_amount") if tds_applicable else None,
                "tds_amount": final_tds_calc.get("tds_amount") if tds_applicable else None,
                "tds_reasoning": final_tds_calc.get("reason"),
            },
            "tds_final": final_tds_calc,
            "tds": final_tds_calc,
            "itc_assessment": itc_result,
        }

        # Deterministic Stage 6 Journal Generator
        journal_result = journal_generator.generate_journal(
            invoice_data=invoice_payload,
            accounting_classification=persisted_accounting_output,
            gst_result=gst_result,
            itc_result=itc_result,
            tds_result=final_tds_calc,
            financial_validation_result=financial_validation_result,
        )

        avg_confidence = None
        if isinstance(accounting_lines, list) and len(accounting_lines) > 0:
            confidences = [
                float(item.get("confidence_score") if item.get("confidence_score") is not None else (item.get("ai_confidence") or 0.0))
                for item in accounting_lines
                if isinstance(item, dict) and (item.get("confidence_score") is not None or item.get("ai_confidence") is not None)
            ]
            if confidences:
                avg_confidence = round(sum(confidences) / len(confidences), 2)

    except Exception as exc:
        logger.exception(f"Error computing downstream accounting for invoice {invoice_id}: {exc}")
        async with AsyncSessionLocal() as session:
            try:
                res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
                inv = res.scalar_one_or_none()
                if inv:
                    inv.status = "FAILED"
                    inv.error_message = str(exc)
                    inv.updated_at = datetime.now(timezone.utc)
                    await session.commit()
            except Exception as commit_exc:
                logger.error(f"Failed to record FAILED status for invoice {invoice_id}: {commit_exc}")
        return

    # Step 3: Persist results in a fresh short-lived session
    async with AsyncSessionLocal() as session:
        try:
            res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
            invoice = res.scalar_one_or_none()
            if not invoice:
                logger.error(f"Invoice {invoice_id} not found during downstream result persistence.")
                return

            invoice.accounting_output = persisted_accounting_output
            invoice.current_accounting_output = persisted_accounting_output
            invoice.gst_result = gst_result
            invoice.itc_result = itc_result
            invoice.financial_validation_result = financial_validation_result
            invoice.journal_entry = journal_result
            invoice.accounting_status = "COMPLETED"
            invoice.status = "COMPLETED"
            invoice.error_message = None
            invoice.updated_at = datetime.now(timezone.utc)
            if avg_confidence is not None:
                invoice.accounting_confidence = avg_confidence

            await sync_relational_journal(session, invoice.id, journal_result)
            await session.commit()
            logger.info(f"Invoice {invoice_id} full Stage 2, 3, 4, 5 & 6 processing completed successfully.")
        except Exception as exc:
            logger.exception(f"Error persisting downstream results for invoice {invoice_id}: {exc}")
            try:
                res = await session.execute(select(Invoice).where(Invoice.id == invoice_id))
                inv = res.scalar_one_or_none()
                if inv:
                    inv.status = "FAILED"
                    inv.error_message = str(exc)
                    inv.updated_at = datetime.now(timezone.utc)
                    await session.commit()
            except Exception as commit_exc:
                logger.error(f"Failed to record FAILED status for invoice {invoice_id}: {commit_exc}")
