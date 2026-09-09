import pytest
from app.services.model_response_adapter import ModelResponseAdapter
from app.services.tds_engine import tds_engine, get_effective_tds_data

def test_tds_calculated_below_30k():
    """Verify that TDS is calculated even if invoice amount is well below 30,000 threshold."""
    low_value_invoice = {
        "invoice_details": {
            "invoice_number": "INV-LOW-001",
            "invoice_date": "2026-09-08",
            "place_of_supply": "36-Telangana",
            "currency": "INR",
            "document_type": "TAX_INVOICE"
        },
        "vendor_details": {
            "name": "Quick IT Tech Solutions",
            "gstin": "36AABCU9603R1ZM",
            "pan": "AABCU9603R"
        },
        "customer_details": {
            "name": "Sakshi Finance",
            "gstin": "36AAACH7409R1ZZ"
        },
        "line_items": [
            {
                "description": "IT Support and Bug Fixes",
                "hsn_sac": "998314",
                "quantity": 1,
                "unit_price": 5000.0,
                "taxable_amount": 5000.0,
                "gst_rate": 18.0,
                "cgst_amount": 450.0,
                "sgst_amount": 450.0
            }
        ],
        "financial_details": {
            "subtotal": 5000.0,
            "taxable_amount": 5000.0,
            "tax_total": 900.0,
            "cgst_amount": 450.0,
            "sgst_amount": 450.0,
            "total_amount": 5900.0
        },
        "tds_support": {
            "tds_applicable_candidate": True,
            "payment_nature": "TECHNICAL_SERVICES",
            "provision_candidate": "194J",
            "base_candidate": 5000.0,
            "rate_candidate": 2.0
        }
    }

    normalized = ModelResponseAdapter.normalize_model_response(low_value_invoice)
    norm_data = normalized["normalized_data"]
    norm_acc = normalized["normalized_accounting"]

    tds_assessment = norm_acc.get("tds_assessment", {})
    assert tds_assessment.get("applicable") is True
    assert tds_assessment.get("section") == "194J"
    assert tds_assessment.get("rate") == 2.0
    assert tds_assessment.get("base_amount") == 5000.0
    assert tds_assessment.get("proposed_tds_amount") == 100.0

    # Test downstream deterministic TDS engine on 5000 base
    effective = get_effective_tds_data({"tds_assessment": tds_assessment})
    base_amt = tds_engine.determine_tds_base_amount(norm_data, effective)
    final_tds = tds_engine.calculate_tds(
        applicable=True,
        section="194J",
        base_amount=base_amt,
        rate=2.0,
        vendor_pan="AABCU9603R"
    )

    assert final_tds["applicable"] is True
    assert final_tds["base_amount"] == 5000.0
    assert final_tds["rate"] == 2.0
    assert final_tds["tds_amount"] == 100.0
