import logging
import uuid
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import select, delete, func, or_, cast, Float
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
from app.services.zoho_client import zoho_client_service
from app.services.invoice_classifier import invoice_classifier, InvoiceClassification
from app.services.forex_service import forex_service

logger = logging.getLogger(__name__)


def convert_foreign_payload_to_inr(payload: Dict[str, Any], exchange_rate: Decimal) -> Dict[str, Any]:
    """
    Converts a foreign service invoice payload into its canonical INR financial representation.
    
    CRITICAL ARCHITECTURAL BOUNDARY:
    - Currency is converted exactly once here.
    - All downstream accounting engines (TDS, GST/RCM, ITC, Financial Validator, Journal)
      receive pure INR numbers from this canonical representation.
    - Original foreign values (currency, total, taxable, line amounts) are preserved.
    """
    if not isinstance(payload, dict):
        return payload

    if not isinstance(exchange_rate, Decimal):
        exchange_rate = Decimal(str(exchange_rate))

    if exchange_rate <= Decimal("0.000000"):
        raise ValueError(f"Exchange rate must be positive Decimal, got: {exchange_rate}")

    converted = dict(payload)
    orig_curr = payload.get("original_currency") or payload.get("currency") or "USD"
    converted["original_currency"] = orig_curr
    converted["currency"] = "INR"
    converted["exchange_rate"] = float(exchange_rate)

    # Convert totals using ForexService Decimal math
    raw_total = payload.get("original_total_amount") if payload.get("original_total_amount") is not None else payload.get("total_amount")
    if raw_total is not None:
        dec_total = Decimal(str(raw_total))
        inr_total = forex_service.convert_to_inr(dec_total, exchange_rate)
        converted["total_amount"] = float(inr_total)
        converted["original_total_amount"] = float(dec_total)
        converted["converted_total_inr"] = float(inr_total)

    raw_taxable = payload.get("original_taxable_amount") if payload.get("original_taxable_amount") is not None else (payload.get("taxable_amount") if payload.get("taxable_amount") is not None else payload.get("subtotal"))
    if raw_taxable is not None:
        dec_taxable = Decimal(str(raw_taxable))
        inr_taxable = forex_service.convert_to_inr(dec_taxable, exchange_rate)
        converted["taxable_amount"] = float(inr_taxable)
        converted["subtotal"] = float(inr_taxable)
        converted["sub_total"] = float(inr_taxable)
        converted["original_taxable_amount"] = float(dec_taxable)
        converted["converted_taxable_inr"] = float(inr_taxable)
        converted["igst_amount"] = round(float(inr_taxable) * 0.18, 2)
        converted["tax_total"] = round(float(inr_taxable) * 0.18, 2)
        converted["cgst_amount"] = 0.0
        converted["sgst_amount"] = 0.0

    # Convert line items
    line_items = payload.get("line_items") or []
    converted_items = []
    for item in line_items:
        if not isinstance(item, dict):
            converted_items.append(item)
            continue
        c_item = dict(item)

        l_taxable = item.get("original_taxable_amount") if item.get("original_taxable_amount") is not None else (item.get("original_line_amount") if item.get("original_line_amount") is not None else (item.get("taxable_amount") if item.get("taxable_amount") is not None else item.get("line_amount")))
        if l_taxable is not None:
            dec_l_taxable = Decimal(str(l_taxable))
            inr_l_taxable = forex_service.convert_to_inr(dec_l_taxable, exchange_rate)
            c_item["taxable_amount"] = float(inr_l_taxable)
            c_item["line_amount"] = float(inr_l_taxable)
            c_item["original_taxable_amount"] = float(dec_l_taxable)
            c_item["original_line_amount"] = float(dec_l_taxable)

        l_unit = item.get("original_unit_price") if item.get("original_unit_price") is not None else (item.get("original_rate") if item.get("original_rate") is not None else (item.get("unit_price") if item.get("unit_price") is not None else item.get("rate")))
        if l_unit is not None:
            dec_l_unit = Decimal(str(l_unit))
            inr_l_unit = forex_service.convert_to_inr(dec_l_unit, exchange_rate)
            c_item["unit_price"] = float(inr_l_unit)
            c_item["rate"] = float(inr_l_unit)
            c_item["original_unit_price"] = float(dec_l_unit)
            c_item["original_rate"] = float(dec_l_unit)

        l_total = item.get("original_total") if item.get("original_total") is not None else item.get("total")
        if l_total is not None:
            dec_l_total = Decimal(str(l_total))
            inr_l_total = forex_service.convert_to_inr(dec_l_total, exchange_rate)
            c_item["total"] = float(inr_l_total)
            c_item["original_total"] = float(dec_l_total)

        # Ensure statutory 18% IGST RCM rate is populated on foreign service line items
        curr_rate = c_item.get("gst_rate") or c_item.get("igst_rate")
        if curr_rate is None or float(curr_rate) == 0.0:
            c_item["gst_rate"] = 18.0
            c_item["igst_rate"] = 18.0
            if c_item.get("taxable_amount") is not None:
                c_item["igst_amount"] = round(float(c_item["taxable_amount"]) * 0.18, 2)

        # Add GST amount into line item total (Taxable + GST)
        if c_item.get("taxable_amount") is not None:
            l_taxable_val = float(c_item["taxable_amount"])
            l_tax_val = float(c_item.get("igst_amount") or 0.0) + float(c_item.get("cgst_amount") or 0.0) + float(c_item.get("sgst_amount") or 0.0) + float(c_item.get("cess_amount") or 0.0)
            c_item["total"] = round(l_taxable_val + l_tax_val, 2)
            if c_item.get("original_taxable_amount") is not None:
                l_orig_taxable = float(c_item["original_taxable_amount"])
                l_orig_tax_rate = float(c_item.get("gst_rate") or c_item.get("igst_rate") or 18.0)
                c_item["original_total"] = round(l_orig_taxable * (1.0 + (l_orig_tax_rate / 100.0)), 2)

        c_item["original_currency"] = orig_curr
        converted_items.append(c_item)

    converted["line_items"] = converted_items
    return converted


def get_effective_invoice_data(invoice: Invoice, convert_fx: bool = False) -> dict:
    """
    Returns complete invoice JSON data for Stage 3 & Stage 4, ensuring base VLM extraction
    fields (line items, totals, vendor/customer, taxes, raw_fields) are fully resolved and preserved.
    If convert_fx=True and invoice is FOREIGN_SERVICE with an active exchange rate,
    converts financial amounts to INR at the single canonical FX boundary.
    """
    from typing import Dict, Any
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
        if not merged.get("invoice_period") and raw_f.get("invoice_period"):
            merged["invoice_period"] = raw_f.get("invoice_period")
        if not merged.get("category") and raw_f.get("category"):
            merged["category"] = raw_f.get("category")
        if not merged.get("due_date") and raw_f.get("due_date"):
            merged["due_date"] = raw_f.get("due_date")
        if not merged.get("vendor_country") and raw_f.get("vendor_country"):
            merged["vendor_country"] = raw_f.get("vendor_country")
        if not merged.get("vendor_tax_id") and raw_f.get("vendor_tax_id"):
            merged["vendor_tax_id"] = raw_f.get("vendor_tax_id")
        if not merged.get("service_period") and raw_f.get("service_period"):
            merged["service_period"] = raw_f.get("service_period")
        if not merged.get("service_description") and raw_f.get("service_description"):
            merged["service_description"] = raw_f.get("service_description")
        if not merged.get("bank_details") and raw_f.get("bank_details"):
            merged["bank_details"] = raw_f.get("bank_details")

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

        # Normalize salary / wage / manpower / duty invoice lines:
        # If invoice contains salary, wages, duties, manpower, cost per person breakdown:
        # Take line item quantity as 1.0 and unit_price as the total taxable amount given.
        # If invoice contains standard quantity and unit price, take as is.
        desc_lower = str(it.get("description") or "").lower()
        unit_lower = str(it.get("unit") or "").lower()
        inv_cat_lower = str(merged.get("category") or "").lower()

        is_salary_wage_duty = any(kw in desc_lower for kw in [
            "salary", "wage", "duties", "duty", "manpower", "security guard", "housekeeping",
            "labour", "labor", "personnel", "guard", "sweeper", "peon", "attendant", "wages",
            "cleaning service", "driver", "care taker", "supervisor"
        ]) or any(kw in unit_lower for kw in [
            "duty", "duties", "day", "days", "shift", "shifts", "person", "persons", "manpower"
        ]) or any(kw in inv_cat_lower for kw in ["salary", "wage", "manpower", "labor", "labour"])

        if is_salary_wage_duty and it.get("taxable_amount") is not None:
            it["quantity"] = 1.0
            it["unit_price"] = float(it["taxable_amount"])

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
        merged["document_date"] = merged["invoice_date"]
    elif merged.get("document_date"):
        merged["document_date"] = parse_and_normalize_date(merged["document_date"])
        merged["invoice_date"] = merged["document_date"]

    if getattr(invoice, "posting_date", None):
        merged["posting_date"] = invoice.posting_date.isoformat() if hasattr(invoice.posting_date, "isoformat") else str(invoice.posting_date)
    elif merged.get("posting_date"):
        merged["posting_date"] = parse_and_normalize_date(merged["posting_date"])
    elif merged.get("invoice_date"):
        merged["posting_date"] = merged.get("invoice_date")

    if merged.get("due_date"):
        merged["due_date"] = parse_and_normalize_date(merged["due_date"])

    if convert_fx:
        origin = getattr(invoice, "invoice_origin", None) or "INDIAN"
        override = getattr(invoice, "classification_override", None)
        active_origin = override or origin
        rate = getattr(invoice, "exchange_rate", None)
        if active_origin == "FOREIGN_SERVICE" and rate:
            return convert_foreign_payload_to_inr(merged, rate)

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
    previous_ytd = 0.0

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

            # Prepare complete single effective invoice JSON for COA, TDS, GST/ITC (converts FX if foreign service)
            invoice_payload = get_effective_invoice_data(invoice, convert_fx=True)
            tenant_id = invoice.tenant_id or "default-tenant-001"
            normalized_accounting_state = invoice.current_accounting_output or invoice.accounting_output
            cached_coa = await master_data_service.get_cached_chart_of_accounts(tenant_id, session)
            cached_taxes = await master_data_service.get_cached_taxes(tenant_id, session)

            # Query historical YTD base amount for same vendor in current Indian Financial Year
            from app.core.date_utils import parse_and_normalize_date, get_indian_financial_year
            raw_inv_date = invoice_payload.get("invoice_date")
            inv_dt_str = parse_and_normalize_date(raw_inv_date) if raw_inv_date else None
            if inv_dt_str:
                try:
                    inv_d = datetime.strptime(inv_dt_str, "%Y-%m-%d").date()
                except ValueError:
                    inv_d = date.today()
            else:
                inv_d = date.today()

            fy_start_year, fy_end_year = get_indian_financial_year(inv_d)

            # Format FY boundary date strings YYYY-MM-DD
            fy_start_str = f"{fy_start_year}-04-01"
            fy_end_str = f"{fy_end_year}-03-31"

            v_pan = invoice_payload.get("vendor_pan") or invoice_payload.get("supplier_pan")
            v_gstin = invoice_payload.get("vendor_gstin") or invoice_payload.get("supplier_gstin")
            v_name = (invoice_payload.get("vendor_name") or invoice_payload.get("supplier_name") or "").strip()

            # Attempt Zoho Books YTD retrieval first
            zoho_ytd_success = False
            try:
                from app.db.models import Vendor
                vendor_query = select(Vendor).where(Vendor.tenant_id == tenant_id)
                v_clauses = []
                if v_pan and len(str(v_pan).strip()) == 10:
                    v_clauses.append(func.lower(Vendor.pan) == str(v_pan).strip().lower())
                if v_gstin and len(str(v_gstin).strip()) == 15:
                    v_clauses.append(func.lower(Vendor.gstin) == str(v_gstin).strip().lower())
                if v_name:
                    v_clauses.append(func.lower(Vendor.vendor_name) == v_name.lower())

                zoho_contact_id = None
                if v_clauses:
                    # Strict priority matching: 1. PAN, 2. GSTIN, 3. Name
                    for clause in v_clauses:
                        v_res = await session.execute(vendor_query.where(clause))
                        matched_v = v_res.scalars().first()
                        if matched_v and matched_v.zoho_contact_id:
                            zoho_contact_id = matched_v.zoho_contact_id
                            break

                if zoho_contact_id:
                    connection = await master_data_service.get_or_create_zoho_connection(tenant_id, session, user_id=invoice.user_id)
                    if connection and connection.status == "CONNECTED" and connection.organization_id:
                        zoho_bills = await zoho_client_service.get_vendor_bills(
                            connection=connection,
                            db=session,
                            vendor_id=zoho_contact_id,
                            date_start=fy_start_str,
                            date_end=fy_end_str,
                        )
                        zoho_sum = 0.0
                        for bill in zoho_bills:
                            b_status = str(bill.get("status") or "").lower()
                            if b_status in ("void", "cancelled", "deleted"):
                                continue

                            # Fetch individual bill detail to get exact pre-tax sub_total
                            # (Summary objects in GET /bills list endpoint omit sub_total and tax_total)
                            b_id = bill.get("bill_id") or bill.get("id")
                            sub_t = bill.get("sub_total")
                            if sub_t is None and b_id:
                                detail = await zoho_client_service.get_bill_detail(
                                    connection=connection,
                                    db=session,
                                    bill_id=str(b_id),
                                )
                                sub_t = detail.get("sub_total")
                                if sub_t is None:
                                    b_tot = detail.get("total")
                                    b_tax = detail.get("tax_total")
                                    if b_tot is not None and b_tax is not None:
                                        sub_t = float(b_tot) - float(b_tax)

                            if sub_t is not None:
                                zoho_sum += float(sub_t)
                            else:
                                logger.warning(f"Could not resolve pre-tax subtotal for Zoho bill '{b_id}'. Skipping from YTD sum.")

                        previous_ytd = float(zoho_sum)
                        zoho_ytd_success = True
                        logger.info(f"Successfully calculated YTD from Zoho vendor bills for vendor '{zoho_contact_id}': ₹{previous_ytd:.2f}")
            except Exception as zoho_exc:
                logger.warning(f"Zoho YTD calculation fallback triggered for invoice {invoice_id}: {zoho_exc}")
                zoho_ytd_success = False

            if not zoho_ytd_success:
                # Fallback to local SAKSHI invoice YTD calculation
                ytd_conditions = []
                if v_pan and len(str(v_pan).strip()) == 10:
                    ytd_conditions.append(func.jsonb_extract_path_text(Invoice.current_vlm_output, 'vendor_pan') == str(v_pan).strip())
                if v_gstin and len(str(v_gstin).strip()) == 15:
                    ytd_conditions.append(func.jsonb_extract_path_text(Invoice.current_vlm_output, 'vendor_gstin') == str(v_gstin).strip())
                if v_name:
                    ytd_conditions.append(func.lower(func.jsonb_extract_path_text(Invoice.current_vlm_output, 'vendor_name')) == v_name.lower())

                if ytd_conditions:
                    subtotal_expr = func.coalesce(
                        cast(func.jsonb_extract_path_text(Invoice.current_vlm_output, 'subtotal'), Float),
                        cast(func.jsonb_extract_path_text(Invoice.current_vlm_output, 'sub_total'), Float),
                        cast(func.jsonb_extract_path_text(Invoice.current_vlm_output, 'taxable_amount'), Float),
                        0.0
                    )
                    inv_date_expr = func.coalesce(
                        func.jsonb_extract_path_text(Invoice.current_vlm_output, 'invoice_date'),
                        func.to_char(Invoice.created_at, 'YYYY-MM-DD')
                    )

                    ytd_query = (
                        select(func.coalesce(func.sum(subtotal_expr), 0.0))
                        .where(
                            Invoice.tenant_id == tenant_id,
                            Invoice.id != invoice_id,
                            Invoice.status != "REJECTED",
                            Invoice.approval_status != "REJECTED",
                            inv_date_expr >= fy_start_str,
                            inv_date_expr <= fy_end_str,
                            or_(*ytd_conditions)
                        )
                    )
                    ytd_res = await session.execute(ytd_query)
                    previous_ytd = float(ytd_res.scalar() or 0.0)

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

        # 3. Call Deterministic Stage 4.5 ITC Engine
        itc_result = itc_engine.evaluate_itc(
            invoice_data=invoice_payload,
            gst_result=gst_result,
            accounting_output=combined_accounting_context if 'combined_accounting_context' in locals() else {"accounting": accounting_lines, "tds_assessment": tds_assessment},
        )

        # 4. Call Deterministic Stage 5 Financial Validator
        financial_validation_result = financial_validator.validate_invoice(invoice_payload, gst_result)

        # 5. Deterministic Final TDS (Authoritative statutory calculation on resolved base amount with threshold state machine)
        from app.services.tds_engine import get_effective_tds_data
        effective_tds = get_effective_tds_data({"tds_assessment": tds_assessment})

        tds_base_amt = tds_engine.determine_tds_base_amount(invoice_payload, effective_tds)
        tds_rate = effective_tds.get("rate")
        tds_section = effective_tds.get("section")
        tds_provision = effective_tds.get("provision")
        tds_nature = effective_tds.get("nature_of_payment")
        vendor_pan = invoice_payload.get("vendor_pan")

        is_foreign = (
            getattr(invoice, "invoice_origin", None) == "FOREIGN_SERVICE"
            or getattr(invoice, "classification_override", None) == "FOREIGN_SERVICE"
            or invoice_payload.get("invoice_origin") == "FOREIGN_SERVICE"
            or invoice_payload.get("classification") == "FOREIGN_SERVICE"
        )
        if is_foreign and effective_tds.get("applicable") is not False:
            tds_section = "Section 393"
            tds_provision = "Section 393(2), Table Sl. No. 17"
            tds_nature = "Non-Resident Payment / Foreign Remittance"
            if not effective_tds.get("is_approved") or tds_rate is None or tds_rate == 0:
                tds_rate = 20.0
            inr_taxable = invoice_payload.get("converted_taxable_inr") or invoice_payload.get("taxable_amount") or invoice_payload.get("subtotal") or invoice_payload.get("total_amount")
            if inr_taxable is not None and float(inr_taxable) > 0:
                tds_base_amt = round(float(inr_taxable), 2)
            previous_ytd = 0.0

        final_tds_calc = tds_engine.calculate_tds(
            applicable=bool(effective_tds.get("applicable")) if effective_tds.get("applicable") is not None else None,
            section=tds_section,
            provision=tds_provision,
            nature_of_payment=tds_nature,
            base_amount=tds_base_amt,
            rate=float(tds_rate) if tds_rate is not None else None,
            vendor_pan=vendor_pan,
            previous_ytd=previous_ytd,
        )
        tds_applicable = bool(final_tds_calc.get("applicable"))

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
                "previous_ytd": final_tds_calc.get("previous_ytd"),
                "projected_ytd": final_tds_calc.get("projected_ytd"),
                "threshold_amount": final_tds_calc.get("threshold_amount"),
                "threshold_status": final_tds_calc.get("threshold_status"),
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

    # 3b. Extract raw document text from PDF via PyMuPDF (fitz) if available
    raw_doc_text = None
    if file_bytes and (not file_mime_type or "pdf" in file_mime_type.lower() or (file_name and file_name.lower().endswith(".pdf"))):
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            extracted_pages = [page.get_text() for page in doc]
            raw_doc_text = "\n".join(extracted_pages)
            doc.close()
        except Exception as pdf_text_err:
            logger.warning(f"Could not extract raw PDF text via PyMuPDF for invoice {invoice_id}: {pdf_text_err}")

    # 4. Normalize model response via ModelResponseAdapter
    from app.services.model_response_adapter import ModelResponseAdapter
    normalized = ModelResponseAdapter.normalize_model_response(
        model_response=raw_model_response,
        user_zoho_coa=cached_coa,
        raw_document_text=raw_doc_text,
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

    # 5. Classify invoice via multi-evidence deterministic classifier (never uses currency alone)
    classification_result = invoice_classifier.classify(
        invoice_data=normalized["normalized_data"],
        raw_document_text=raw_doc_text,
    )
    detected_origin = classification_result.classification.value
    extracted_currency = classification_result.currency
    
    raw_total = normalized["normalized_data"].get("total_amount")
    raw_taxable = normalized["normalized_data"].get("taxable_amount") or normalized["normalized_data"].get("subtotal")
    
    orig_total_dec = Decimal(str(raw_total)) if raw_total is not None else None
    orig_taxable_dec = Decimal(str(raw_taxable)) if raw_taxable is not None else None

    fx_rate_val = None
    fx_rate_date = None
    fx_rate_source = None
    conv_total_inr = None
    conv_taxable_inr = None

    if classification_result.classification == InvoiceClassification.FOREIGN_SERVICE:
        from app.core.date_utils import parse_and_normalize_date
        inv_d_str = normalized["normalized_data"].get("invoice_date")
        inv_d_parsed = None
        if inv_d_str:
            try:
                norm_d = parse_and_normalize_date(inv_d_str)
                inv_d_parsed = datetime.strptime(norm_d, "%Y-%m-%d").date() if norm_d else None
            except Exception:
                inv_d_parsed = None

        proc_d = datetime.now(timezone.utc).date()
        target_fx_date = forex_service.resolve_fx_date(
            invoice_date=inv_d_parsed,
            processing_date=proc_d,
        )

        fx_res = await forex_service.get_exchange_rate(
            currency=extracted_currency,
            fx_date=target_fx_date,
        )
        fx_rate_val = fx_res.rate
        fx_rate_date = fx_res.rate_date
        fx_rate_source = fx_res.source

        if orig_total_dec is not None:
            conv_total_inr = forex_service.convert_to_inr(orig_total_dec, fx_rate_val)
        if orig_taxable_dec is not None:
            conv_taxable_inr = forex_service.convert_to_inr(orig_taxable_dec, fx_rate_val)

    # Determine status based on classification outcome
    if classification_result.classification == InvoiceClassification.INDIAN:
        next_status = "PROCESSING_ACCOUNTING"
    elif classification_result.classification == InvoiceClassification.FOREIGN_SERVICE:
        next_status = "PROCESSING_ACCOUNTING"
    elif classification_result.classification == InvoiceClassification.UNSUPPORTED_FOREIGN_GOODS:
        next_status = "UNSUPPORTED"
    else:  # REVIEW_REQUIRED
        next_status = "PENDING_REVIEW"

    async with AsyncSessionLocal() as session:
        try:
            query = select(Invoice).where(Invoice.id == invoice_id)
            result = await session.execute(query)
            invoice = result.scalar_one_or_none()
            if invoice:
                invoice.raw_vlm_output = raw_snapshot
                if classification_result.classification == InvoiceClassification.FOREIGN_SERVICE and fx_rate_val:
                    inr_vlm_data = convert_foreign_payload_to_inr(normalized["normalized_data"], fx_rate_val)
                    invoice.current_vlm_output = {"data": inr_vlm_data}
                else:
                    invoice.current_vlm_output = norm_vlm_dict
                invoice.accounting_output = norm_accounting_dict
                invoice.current_accounting_output = norm_accounting_dict
                invoice.invoice_origin = detected_origin
                invoice.currency = "INR" if classification_result.classification == InvoiceClassification.FOREIGN_SERVICE else extracted_currency
                invoice.original_currency = extracted_currency
                invoice.original_total_amount = orig_total_dec
                invoice.original_taxable_amount = orig_taxable_dec
                invoice.exchange_rate = fx_rate_val
                invoice.fx_original_rate = fx_rate_val
                invoice.exchange_rate_date = fx_rate_date
                invoice.exchange_rate_source = fx_rate_source
                invoice.converted_total_inr = conv_total_inr
                invoice.converted_taxable_inr = conv_taxable_inr
                invoice.fx_rate_overridden = False
                invoice.classification_confidence = classification_result.confidence
                invoice.classification_reason = classification_result.reason
                invoice.classification_model = "RULE_ENGINE_V1"
                invoice.classification_source = "SYSTEM"
                invoice.classified_at = datetime.now(timezone.utc)
                invoice.status = next_status
                invoice.period_category = period_category
                invoice.period_decision = period_decision
                if classification_result.classification == InvoiceClassification.UNSUPPORTED_FOREIGN_GOODS:
                    invoice.error_message = classification_result.reason
                invoice.updated_at = datetime.now(timezone.utc)
                await session.commit()
                logger.info(
                    f"Invoice {invoice_id} extraction complete "
                    f"(origin: {detected_origin}, currency: {extracted_currency}, status: {next_status}, "
                    f"confidence: {classification_result.confidence}, reason: {classification_result.reason})."
                )
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

    # 6. Execute downstream Stage 3-6 Deterministic Engines for domestic Indian and Foreign Service pipelines
    # Foreign goods and review-required items are held safely at the classification gate
    if classification_result.classification in (InvoiceClassification.INDIAN, InvoiceClassification.FOREIGN_SERVICE):
        await process_accounting_downstream_background(invoice_id)


async def process_accounting_downstream_background(invoice_id) -> None:
    logger.info(f"Starting downstream accounting processing for approved HITL invoice {invoice_id}")
    tenant_id = None
    extraction_result = None
    cached_coa = None
    cached_taxes = None
    invoice_payload = None

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
            raw_vlm_output = invoice.raw_vlm_output or {}

            # Prepare canonical effective invoice payload (converts FX to INR once if foreign service)
            invoice_payload = get_effective_invoice_data(invoice, convert_fx=True)

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
        if not invoice_payload:
            invoice_payload = extraction_result.get("data") if isinstance(extraction_result, dict) and "data" in extraction_result else (extraction_result or {})

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

        is_foreign = (
            getattr(invoice, "invoice_origin", None) == "FOREIGN_SERVICE"
            or getattr(invoice, "classification_override", None) == "FOREIGN_SERVICE"
            or invoice_payload.get("invoice_origin") == "FOREIGN_SERVICE"
            or invoice_payload.get("classification") == "FOREIGN_SERVICE"
        )
        if is_foreign and effective_tds.get("applicable") is not False:
            tds_section = "Section 393"
            tds_provision = "Section 393(2), Table Sl. No. 17"
            tds_nature = "Non-Resident Payment / Foreign Remittance"
            if not effective_tds.get("is_approved") or tds_rate is None or tds_rate == 0:
                tds_rate = 20.0
            inr_taxable = invoice_payload.get("converted_taxable_inr") or invoice_payload.get("taxable_amount") or invoice_payload.get("subtotal") or invoice_payload.get("total_amount")
            if inr_taxable is not None and float(inr_taxable) > 0:
                tds_base_amt = round(float(inr_taxable), 2)

        vendor_decl_data = (
            tds_assessment.get("vendor_declared_tds")
            or (normalized_accounting_state.get("vendor_declared_tds") if isinstance(normalized_accounting_state, dict) else None)
        )

        final_tds_calc = tds_engine.calculate_tds(
            applicable=tds_applicable,
            section=tds_section,
            provision=tds_provision,
            nature_of_payment=tds_nature,
            base_amount=tds_base_amt,
            rate=float(tds_rate) if tds_rate is not None else None,
            vendor_pan=vendor_pan,
            vendor_declared_tds=vendor_decl_data,
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
                "vendor_declared_tds": vendor_decl_data,
                "tds_needs_review": final_tds_calc.get("tds_needs_review", False),
                "tds_conflict_code": final_tds_calc.get("tds_conflict_code"),
                "tds_conflict_reason": final_tds_calc.get("tds_conflict_reason"),
            },
            "tds_final": final_tds_calc,
            "tds": final_tds_calc,
            "vendor_declared_tds": vendor_decl_data,
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
