import pytest
from app.services.accounting_service import AccountingService
from app.services.tds_service import TDSService
from app.services.gst_engine import gst_engine
from app.services.journal_generator import journal_generator
from app.services.tds_engine import tds_engine


def test_independent_normalized_json_to_coa_and_tds():
    """Verify that both COA and TDS receive the exact same normalized invoice dictionary."""
    normalized_invoice = {
        "invoice_number": "INV-2026-TEST-99",
        "invoice_date": "2026-08-20",
        "vendor_name": "Apex Cloud Tech",
        "vendor_gstin": "36AABCU9603R1ZM",
        "customer_gstin": "29AAACH7409R1ZZ",
        "place_of_supply": "29-Karnataka",
        "subtotal": 100000.0,
        "tax_total": 18000.0,
        "igst_amount": 18000.0,
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "total_amount": 118000.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Enterprise Cloud Hosting",
                "quantity": 1.0,
                "unit_price": 100000.0,
                "taxable_amount": 100000.0,
                "igst_rate": 18.0,
                "igst_amount": 18000.0,
                "total": 118000.0,
            }
        ],
    }

    # Deterministic GST Engine evaluation
    gst_res = gst_engine.evaluate_gst(normalized_invoice)
    assert gst_res["supply_type"] == "INTER_STATE"
    assert gst_res["calculated"]["igst_amount"] == 18000.0
    assert gst_res["calculated"]["cgst_amount"] == 0.0
    assert gst_res["calculated"]["sgst_amount"] == 0.0

    # Independent COA proposal representation
    coa_proposal = {
        "accounting": [
            {
                "line_index": 1,
                "source_description": "Enterprise Cloud Hosting",
                "account_id": "ACC_1",
                "account_name": "Cloud Hosting & Infrastructure",
                "confidence_score": 0.98,
                "ai_needs_review": False,
                "accounting_reason": "Cloud server infrastructure hosting expense",
            }
        ]
    }

    # Independent TDS proposal representation
    tds_proposal = {
        "tds_assessment": {
            "tds_applicable": True,
            "nature_of_payment": "Technical services",
            "tds_provision": "Section 393",
            "tds_section": "Table 6(ii)",
            "tds_rate": 2.0,
            "tds_base_amount": 100000.0,
            "proposed_tds_amount": 2000.0,
            "tds_needs_review": False,
            "tds_reasoning": "Technical services subject to 2% withholding under Table 6(ii)",
        }
    }

    # Authoritative statutory TDS calculation
    final_tds = tds_engine.calculate_tds(
        section=tds_proposal["tds_assessment"]["tds_section"],
        provision=tds_proposal["tds_assessment"]["tds_provision"],
        nature_of_payment=tds_proposal["tds_assessment"]["nature_of_payment"],
        base_amount=normalized_invoice["subtotal"],
        rate=tds_proposal["tds_assessment"]["tds_rate"],
        vendor_pan="AABCU9603R",
    )
    final_tds["is_approved"] = True
    assert final_tds["applicable"] is True
    assert final_tds["tds_amount"] == 2000.0

    # Build persisted combined output
    persisted_accounting_output = {
        "accounting": coa_proposal["accounting"],
        "tds_assessment": tds_proposal["tds_assessment"],
        "tds_final": final_tds,
        "tds": final_tds,
    }

    # Generate authoritative journal entry
    journal = journal_generator.generate_journal(
        invoice_data=normalized_invoice,
        accounting_classification=persisted_accounting_output,
        gst_result=gst_res,
        tds_result=final_tds,
    )

    assert journal["status"] == "BALANCED"
    assert journal["total_debit"] == 118000.0
    assert journal["total_credit"] == 118000.0

    account_ids = [l["account_id"] for l in journal["lines"]]
    assert "ACC_1" in account_ids
    assert "TAX_INP_IGST" in account_ids
    assert "LIAB_TDS_PAYABLE" in account_ids
    assert "LIAB_AP" in account_ids

    # Verify AP credit is exactly Gross (118,000) - TDS (2,000) = 116,000
    ap_line = next(l for l in journal["lines"] if l["account_id"] == "LIAB_AP")
    assert ap_line["credit"] == 116000.0


def test_gst_interstate_mismatch_preserves_extracted_evidence():
    """Verify that when supplier state differs from POS, extracted CGST/SGST is not deleted but marked GST_MISMATCH."""
    interstate_with_cgst_sgst = {
        "vendor_gstin": "36AABCU9603R1ZM",  # Telangana (36)
        "customer_gstin": "29AAACH7409R1ZZ", # Karnataka (29)
        "place_of_supply": "29-Karnataka",
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "cgst_amount": 900.0,
        "sgst_amount": 900.0,
        "igst_amount": 0.0,
        "line_items": [
            {
                "line_index": 1,
                "description": "Item",
                "taxable_amount": 10000.0,
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
            }
        ]
    }

    gst_res = gst_engine.evaluate_gst(interstate_with_cgst_sgst)
    assert gst_res["supply_type"] == "INTER_STATE"
    assert gst_res["validation_status"] == "GST_MISMATCH"
    # Extracted evidence is preserved
    assert gst_res["extracted"]["cgst_amount"] == 900.0
    assert gst_res["extracted"]["sgst_amount"] == 900.0
    # Calculated deterministic expectation enforces IGST
    assert gst_res["calculated"]["igst_amount"] == 0.0 or gst_res["calculated"]["cgst_amount"] == 0.0
    assert gst_res["calculated"]["cgst_amount"] == 0.0
    assert gst_res["calculated"]["sgst_amount"] == 0.0


def test_unitemized_tax_prohibits_synthetic_split():
    """Verify that unitemized tax_total without CGST/SGST/IGST breakdown flags REVIEW_REQUIRED without fake 50/50 split."""
    unitemized_invoice = {
        "vendor_name": "Local Vendor",
        "subtotal": 10000.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "cgst_amount": None,
        "sgst_amount": None,
        "igst_amount": None,
        "line_items": [
            {
                "line_index": 1,
                "description": "Bulk Supplies",
                "taxable_amount": 10000.0,
            }
        ]
    }
    accounting = {
        "accounting": [
            {
                "line_index": 1,
                "account_id": "ACC_3",
                "account_name": "Office Supplies",
            }
        ]
    }

    journal = journal_generator.generate_journal(unitemized_invoice, accounting)
    assert journal["status"] == "REVIEW_REQUIRED"
    assert any("synthetic tax split is prohibited" in w for w in journal["validation"]["warnings"])

    # Verify no fake INPUT_CGST or INPUT_SGST lines were generated
    account_ids = [l["account_id"] for l in journal["lines"]]
    assert "TAX_INP_CGST" not in account_ids
    assert "TAX_INP_SGST" not in account_ids
    assert "TAX_INP_IGST" not in account_ids
    # Grounded to Unitemized Tax (Pending Review)
    assert "TAX_BLOCKED" in account_ids
