import pytest
import os
import json
import asyncio
from app.core.config import settings
from app.services.ai_service import ai_service
from app.services.accounting_service import accounting_service, DEFAULT_CHART_OF_ACCOUNTS, DEFAULT_AVAILABLE_TAXES
from app.services.tds_service import tds_service
from app.services.gst_engine import gst_engine
from app.services.itc_engine import itc_engine
from app.services.financial_validator import financial_validator
from app.services.tds_engine import tds_engine
from app.services.journal_generator import journal_generator


@pytest.mark.asyncio
async def test_live_interstate_invoice_e2e():
    """
    Real backend-only live E2E test with Qwen3-VL, Qwen3-4B COA, and Groq/Qwen TDS
    for an Inter-State Invoice (Karnataka -> Telangana).
    """
    image_path = os.path.join("scratch", "invoice_interstate_29_to_36.png")
    assert os.path.exists(image_path), f"Test invoice image not found at {image_path}"

    with open(image_path, "rb") as f:
        file_bytes = f.read()

    print("\n========================================================")
    print(">>> [TEST 1] INTER-STATE INVOICE E2E (KARNATAKA -> TELANGANA)")
    print("========================================================")

    # 1. Real VLM Extraction
    print("\n--- 1. Qwen3-VL Extraction ---")
    vlm_res = await ai_service.extract_invoice_vlm(file_bytes)
    assert isinstance(vlm_res, dict), "VLM response must be a dict"
    assert "data" in vlm_res, "VLM response missing 'data' key"
    
    extracted_data = vlm_res["data"]
    print("Extracted Invoice JSON:")
    print(json.dumps(extracted_data, indent=2))

    # Verify extracted invoice fields
    vendor_gstin = extracted_data.get("vendor_gstin") or ""
    assert "29" in vendor_gstin, f"Expected Karnataka (29) GSTIN, got {vendor_gstin}"
    pos = extracted_data.get("place_of_supply") or (extracted_data.get("additional_fields") or {}).get("Place of Supply") or ""
    assert "36" in pos or "Telangana" in pos, f"Expected Telangana (36) POS, got {pos}"

    # 2. Concurrent COA & TDS dispatch with IDENTICAL normalized invoice JSON
    print("\n--- 2. Dispatching IDENTICAL Normalized JSON to COA and TDS ---")
    coa_task = accounting_service.categorize_accounting(
        invoice_json=extracted_data,
        chart_of_accounts=DEFAULT_CHART_OF_ACCOUNTS,
        available_taxes=DEFAULT_AVAILABLE_TAXES,
    )
    tds_task = tds_service.assess_tds(
        invoice_json=extracted_data,
    )

    coa_res, tds_res = await asyncio.gather(coa_task, tds_task)

    print("\n--- 3. Qwen3-4B COA Response ---")
    print(json.dumps(coa_res, indent=2))
    assert "accounting" in coa_res, "COA response missing 'accounting' array"
    assert len(coa_res["accounting"]) > 0, "COA response has empty accounting lines"
    first_acct = coa_res["accounting"][0]
    assert first_acct.get("account_id") is not None, "account_id should not be None for valid item"
    assert first_acct.get("account_id") != "ACC_1" or "Cloud" in (first_acct.get("account_name") or ""), "COA mapped appropriately"

    print("\n--- 4. Groq/Qwen TDS Response ---")
    print(json.dumps(tds_res, indent=2))
    assert "tds_assessment" in tds_res, "TDS response missing 'tds_assessment'"
    tds_assess = tds_res["tds_assessment"]
    assert "tds_applicable" in tds_assess, "TDS assessment missing 'tds_applicable'"

    # 3. Deterministic GST Engine Verification
    print("\n--- 5. Deterministic GST Engine ---")
    gst_res = gst_engine.evaluate_gst(extracted_data)
    print("GST Engine Result:")
    print(json.dumps(gst_res, indent=2))

    assert gst_res["supply_type"] == "INTER_STATE", f"Expected INTER_STATE supply, got {gst_res['supply_type']}"
    assert gst_res["calculated"]["igst_amount"] > 0, "Calculated IGST must be > 0"
    assert gst_res["calculated"]["cgst_amount"] == 0.0, "Calculated CGST must be 0 for INTER_STATE"
    assert gst_res["calculated"]["sgst_amount"] == 0.0, "Calculated SGST must be 0 for INTER_STATE"

    # 4. Deterministic ITC Engine Verification
    print("\n--- 6. Deterministic ITC Engine ---")
    combined_accounting = {
        "accounting": coa_res["accounting"],
        "tds_assessment": tds_assess,
    }
    itc_res = itc_engine.evaluate_itc(extracted_data, combined_accounting)
    print("ITC Result:")
    print(json.dumps(itc_res, indent=2))
    assert itc_res["status"] == "ELIGIBLE"

    # 5. Deterministic Financial Validator
    print("\n--- 7. Deterministic Financial Validator ---")
    fin_val = financial_validator.validate_invoice(extracted_data, gst_res)
    print("Financial Validation Result:")
    print(json.dumps(fin_val, indent=2))
    assert fin_val["overall_status"] == "PASSED"

    # 6. Final Statutory TDS Calculation
    print("\n--- 8. Authoritative Statutory TDS ---")
    subtotal = float(extracted_data.get("subtotal") or 0.0)
    final_tds = tds_engine.calculate_tds(
        section=tds_assess.get("tds_section"),
        provision=tds_assess.get("tds_provision"),
        nature_of_payment=tds_assess.get("nature_of_payment"),
        base_amount=subtotal,
        rate=tds_assess.get("tds_rate"),
        vendor_pan=extracted_data.get("vendor_pan"),
    )
    final_tds["is_approved"] = True
    print("Final TDS:", final_tds)

    # 7. Authoritative Journal Generation
    print("\n--- 9. Authoritative Balanced Journal ---")
    persisted_output = {
        "accounting": coa_res["accounting"],
        "tds_assessment": tds_assess,
        "tds_final": final_tds,
        "tds": final_tds,
    }
    journal = journal_generator.generate_journal(
        invoice_data=extracted_data,
        accounting_classification=persisted_output,
        gst_result=gst_res,
        itc_result=itc_res,
        tds_result=final_tds,
        financial_validation_result=fin_val,
    )
    print("Journal Result:")
    print(json.dumps(journal, indent=2))

    assert journal["status"] == "BALANCED", f"Journal status expected BALANCED, got {journal['status']}"
    assert journal["validation"]["balanced"] is True
    assert journal["total_debit"] == journal["total_credit"]

    # Tax accounts verification: ONLY Input IGST, NO Input CGST/SGST
    account_ids = [l["account_id"] for l in journal["lines"]]
    assert "TAX_INP_IGST" in account_ids, "Input IGST must be present in Inter-State journal"
    assert "TAX_INP_CGST" not in account_ids, "Input CGST must NOT be present in Inter-State journal"
    assert "TAX_INP_SGST" not in account_ids, "Input SGST must NOT be present in Inter-State journal"


@pytest.mark.asyncio
async def test_live_intrastate_invoice_e2e():
    """
    Real backend-only live E2E test with Qwen3-VL, Qwen3-4B COA, and Groq/Qwen TDS
    for an Intra-State Invoice (Telangana -> Telangana).
    """
    image_path = os.path.join("scratch", "invoice_intrastate_36_to_36.png")
    assert os.path.exists(image_path), f"Test invoice image not found at {image_path}"

    with open(image_path, "rb") as f:
        file_bytes = f.read()

    print("\n========================================================")
    print(">>> [TEST 2] INTRA-STATE INVOICE E2E (TELANGANA -> TELANGANA)")
    print("========================================================")

    # 1. Real VLM Extraction
    print("\n--- 1. Qwen3-VL Extraction ---")
    vlm_res = await ai_service.extract_invoice_vlm(file_bytes)
    assert isinstance(vlm_res, dict)
    assert "data" in vlm_res
    extracted_data = vlm_res["data"]
    print("Extracted Invoice JSON:")
    print(json.dumps(extracted_data, indent=2))

    # 2. Concurrent COA & TDS
    print("\n--- 2. Concurrent COA & TDS with Identical JSON ---")
    coa_task = accounting_service.categorize_accounting(
        invoice_json=extracted_data,
        chart_of_accounts=DEFAULT_CHART_OF_ACCOUNTS,
        available_taxes=DEFAULT_AVAILABLE_TAXES,
    )
    tds_task = tds_service.assess_tds(
        invoice_json=extracted_data,
    )

    coa_res, tds_res = await asyncio.gather(coa_task, tds_task)
    print("\n--- 3. Qwen3-4B COA Result ---")
    print(json.dumps(coa_res, indent=2))
    print("\n--- 4. Groq/Qwen TDS Result ---")
    print(json.dumps(tds_res, indent=2))

    # 3. Deterministic GST Engine Verification
    print("\n--- 5. Deterministic GST Engine ---")
    gst_res = gst_engine.evaluate_gst(extracted_data)
    print(json.dumps(gst_res, indent=2))

    assert gst_res["supply_type"] == "INTRA_STATE", f"Expected INTRA_STATE supply, got {gst_res['supply_type']}"
    assert gst_res["calculated"]["cgst_amount"] > 0, "Calculated CGST must be > 0"
    assert gst_res["calculated"]["sgst_amount"] > 0, "Calculated SGST must be > 0"
    assert gst_res["calculated"]["igst_amount"] == 0.0, "Calculated IGST must be 0 for INTRA_STATE"

    # 4. Final Statutory TDS & Journal
    subtotal = float(extracted_data.get("subtotal") or 0.0)
    tds_assess = tds_res.get("tds_assessment") or {}
    final_tds = tds_engine.calculate_tds(
        section=tds_assess.get("tds_section"),
        provision=tds_assess.get("tds_provision"),
        nature_of_payment=tds_assess.get("nature_of_payment"),
        base_amount=subtotal,
        rate=tds_assess.get("tds_rate"),
        vendor_pan=extracted_data.get("vendor_pan"),
    )
    final_tds["is_approved"] = True

    persisted_output = {
        "accounting": coa_res["accounting"],
        "tds_assessment": tds_assess,
        "tds_final": final_tds,
        "tds": final_tds,
    }
    itc_res = itc_engine.evaluate_itc(extracted_data, persisted_output)
    fin_val = financial_validator.validate_invoice(extracted_data, gst_res)

    journal = journal_generator.generate_journal(
        invoice_data=extracted_data,
        accounting_classification=persisted_output,
        gst_result=gst_res,
        itc_result=itc_res,
        tds_result=final_tds,
        financial_validation_result=fin_val,
    )
    print("\n--- 6. Authoritative Journal ---")
    print(json.dumps(journal, indent=2))

    assert journal["status"] == "BALANCED"
    assert journal["validation"]["balanced"] is True

    account_ids = [l["account_id"] for l in journal["lines"]]
    assert "TAX_INP_CGST" in account_ids, "Input CGST must be present in Intra-State journal"
    assert "TAX_INP_SGST" in account_ids, "Input SGST must be present in Intra-State journal"
    assert "TAX_INP_IGST" not in account_ids, "Input IGST must NOT be present in Intra-State journal"
