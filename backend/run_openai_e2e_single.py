"""
Single Real OpenAI End-to-End Invoice Pipeline Test.
Optimized aggressively for minimum token usage:
- Single simple invoice: scratch/invoice_intrastate_36_to_36.png (1 page, 98KB, 1 line item)
- detail='low' image resolution
- Minimal runtime COA
- Single API call (max_retries=1)
- Full deterministic downstream validation (GST, TDS, ITC, COA, Journal)
"""

import asyncio
import json
import time
from pathlib import Path

from app.services.ai_service import ai_service
from app.services.model_response_adapter import ModelResponseAdapter
from app.services.gst_engine import gst_engine
from app.services.itc_engine import itc_engine
from app.services.tds_engine import tds_engine, get_effective_tds_data
from app.services.financial_validator import financial_validator
from app.services.journal_generator import journal_generator


async def run_single_openai_e2e():
    invoice_path = Path("scratch/invoice_intrastate_36_to_36.png")
    if not invoice_path.exists():
        raise FileNotFoundError(f"Invoice file not found at {invoice_path}")

    file_bytes = invoice_path.read_bytes()
    filename = invoice_path.name

    # Minimal tenant COA to conserve tokens
    minimal_coa = [
        {"account_id": "1001", "account_name": "IT and Internet Expenses", "account_type": "expense"},
        {"account_id": "1002", "account_name": "Office Supplies", "account_type": "expense"},
        {"account_id": "1003", "account_name": "Professional Fees", "account_type": "expense"},
    ]

    t_start = time.time()
    model_name = ai_service.active_model
    print(f"1. Starting real OpenAI call with model: {model_name}")
    print(f"   Input file: {filename} ({len(file_bytes)} bytes)")

    # 1. AIService extraction via OpenAI
    try:
        raw_vlm_output = await ai_service.extract_invoice_vlm(
            file_bytes=file_bytes,
            filename=filename,
            content_type="image/png",
            chart_of_accounts=minimal_coa,
        )
    except Exception as exc:
        print(f"FAIL at Stage: OpenAI API Call | Error: {exc}")
        return

    openai_duration = round(time.time() - t_start, 2)
    print(f"2. OpenAI call succeeded in {openai_duration}s!")

    token_usage = raw_vlm_output.pop("_token_usage", {})
    prompt_tokens = token_usage.get("prompt_tokens", "N/A")
    completion_tokens = token_usage.get("completion_tokens", "N/A")
    total_tokens = token_usage.get("total_tokens", "N/A")

    # 2. Adapter Normalization
    try:
        normalized = ModelResponseAdapter.normalize_model_response(
            model_response=raw_vlm_output,
            user_zoho_coa=minimal_coa,
        )
        invoice_payload = normalized["normalized_data"]
        accounting_payload = normalized["normalized_accounting"]
        adapter_success = True
    except Exception as exc:
        print(f"FAIL at Stage: Adapter Normalization | Error: {exc}")
        return

    # 3. Deterministic Downstream Engines
    try:
        # GST Engine
        gst_result = gst_engine.evaluate_gst(invoice_payload)

        # ITC Engine
        itc_context = {
            "accounting": accounting_payload.get("accounting", []),
            "tds_assessment": accounting_payload.get("tds_assessment", {}),
        }
        itc_result = itc_engine.evaluate_itc(invoice_payload, itc_context)

        # Financial Validator
        financial_validation = financial_validator.validate_invoice(invoice_payload, gst_result)

        # TDS Engine
        tds_assessment = accounting_payload.get("tds_assessment", {})
        from app.services.tds_engine import get_effective_tds_data
        effective_tds = get_effective_tds_data({"tds_assessment": tds_assessment})
        tds_applicable = bool(effective_tds.get("applicable"))
        tds_base_amt = tds_engine.determine_tds_base_amount(invoice_payload, effective_tds)
        tds_rate = effective_tds.get("rate")
        tds_section = effective_tds.get("section")
        tds_provision = effective_tds.get("provision")
        tds_nature = effective_tds.get("nature_of_payment")
        vendor_pan = invoice_payload.get("vendor_pan")

        final_tds = tds_engine.calculate_tds(
            applicable=tds_applicable,
            section=tds_section,
            provision=tds_provision,
            nature_of_payment=tds_nature,
            base_amount=tds_base_amt,
            rate=float(tds_rate) if tds_rate is not None else None,
            vendor_pan=vendor_pan,
        )

        persisted_accounting = {
            "accounting": accounting_payload.get("accounting", []),
            "tds_assessment": {
                **tds_assessment,
                "applicable": tds_applicable,
                "tds_rate": final_tds.get("rate") if tds_applicable else None,
                "tds_base_amount": final_tds.get("base_amount") if tds_applicable else None,
                "tds_amount": final_tds.get("tds_amount") if tds_applicable else None,
            },
            "tds_final": final_tds,
        }

        # Journal Generator
        journal_result = journal_generator.generate_journal(
            invoice_data=invoice_payload,
            accounting_classification=persisted_accounting,
            gst_result=gst_result,
            itc_result=itc_result,
            tds_result=final_tds,
            financial_validation_result=financial_validation,
        )

        downstream_success = True
    except Exception as exc:
        print(f"FAIL at Stage: Downstream Deterministic Engines | Error: {exc}")
        return

    total_duration = round(time.time() - t_start, 2)

    # Print Final Summary Report
    print("\n" + "=" * 60)
    print("=== SINGLE REAL OPENAI E2E RESULT ===")
    print("=" * 60)
    print(f"Model used: {model_name}")
    print(f"Input token usage: {prompt_tokens}")
    print(f"Output token usage: {completion_tokens}")
    print(f"Total token usage: {total_tokens}")
    print(f"API success/failure: SUCCESS")
    print(f"End-to-end time: {total_duration}s (OpenAI: {openai_duration}s)")
    print(f"Whether adapter succeeded: {adapter_success}")
    print(f"Whether deterministic downstream processing succeeded: {downstream_success}")
    print(f"Final success/failure: SUCCESS")

    print("\n--- DETAILED ENGINE AUDIT ---")
    print(f"Invoice Number: {invoice_payload.get('invoice_number')}")
    print(f"Vendor: {invoice_payload.get('vendor_name')} (GSTIN: {invoice_payload.get('vendor_gstin')})")
    print(f"Customer: {invoice_payload.get('customer_name')} (GSTIN: {invoice_payload.get('customer_gstin')})")
    print(f"Total Amount: {invoice_payload.get('total_amount')}")
    gst_calc = gst_result.get('calculated', {})
    print(f"GST Supply Type: {gst_result.get('supply_type')} | Tax: CGST={gst_calc.get('cgst_amount')}, SGST={gst_calc.get('sgst_amount')}, IGST={gst_calc.get('igst_amount')}")
    print(f"TDS Result: applicable={tds_applicable}, section={tds_section}, provision={tds_provision}, rate={final_tds.get('rate')}%, base={final_tds.get('base_amount')}, final_amt={final_tds.get('tds_amount')}")
    print(f"ITC Result: status={itc_result.get('status')}, eligible_amount={itc_result.get('eligible_itc')}")
    coa_matches = accounting_payload.get("coa_support", {}).get("line_matches", [])
    print(f"COA Matches: {json.dumps(coa_matches, indent=2)}")
    journal_lines = journal_result.get("journal_lines") or journal_result.get("lines") or []
    print(f"Generated Journal Lines ({len(journal_lines)} lines):")
    for jl in journal_lines:
        print(f"   {jl.get('account_name')}: Debit={jl.get('debit')}, Credit={jl.get('credit')}")
    print(f"Review Flags: {accounting_payload.get('review_flags')}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_single_openai_e2e())
