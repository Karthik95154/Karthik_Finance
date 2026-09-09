import pytest
from app.services.model_response_adapter import ModelResponseAdapter


def test_kimi_locked_schema_cases():
    # 1. Normal invoice + absent charges remaining None
    raw_kimi_absent_charges = {
        "schema_version": "2.3.0",
        "invoice_details": {"invoice_number": "INV-1001"},
        "vendor_details": {"name": "Vendor A", "gstin": "27ABCDE1234F1Z5"},
        "customer_details": {"name": "Customer B", "gstin": "27XYZAB5678C1Z3"},
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 1,
                "unit_price": 1000.0,
                "line_amount": 1000.0,
                "taxable_amount": 1000.0,
                "cgst_rate": 9.0,
                "cgst_amount": 90.0,
                "sgst_rate": 9.0,
                "sgst_amount": 90.0,
                "total_amount": 1180.0
            }
        ],
        "financial_details": {
            "subtotal": 1000.0,
            "tax_total": 180.0,
            "total_amount": 1180.0
        },
        "coa_support": {
            "line_matches": [
                {
                    "line_index": 0,
                    "matched_account_id": "ACC_ZOHO_1",
                    "matched_account_name": "Office Supplies",
                    "match_type": "EXACT",
                    "confidence": 0.99,
                    "requires_review": False,
                    "reason": "Exact COA match"
                }
            ]
        }
    }

    mock_coa = [{"account_id": "ACC_ZOHO_1", "account_name": "Office Supplies"}]
    res = ModelResponseAdapter.normalize_model_response(raw_kimi_absent_charges, mock_coa)

    data = res["normalized_data"]
    acct = res["normalized_accounting"]

    # Test absent financial charges stay None
    assert data["shipping_charges"] is None
    assert data["other_charges"] is None
    assert data["adjustment"] is None
    assert data["round_off"] is None

    # Test vendor PAN derived from vendor GSTIN (and customer PAN from customer GSTIN)
    assert data["vendor_pan"] == "ABCDE1234F"
    assert data["customer_pan"] == "XYZAB5678C"

    # Test COA match via 0-indexed line_matches
    assert len(acct["accounting"]) == 1
    assert acct["accounting"][0]["line_index"] == 1  # Display 1-based index
    assert acct["accounting"][0]["match_status"] == "EXACT_MATCH"
    assert acct["accounting"][0]["account_id"] == "ACC_ZOHO_1"
    assert acct["accounting"][0]["account_name"] == "Office Supplies"


def test_kimi_explicit_zero_charges():
    raw_kimi = {
        "schema_version": "2.3.0",
        "financial_details": {
            "subtotal": 1000.0,
            "shipping_charges": 0.0,
            "other_charges": 0.0,
            "adjustment": 0.0,
            "round_off": 0.0,
            "total_amount": 1000.0
        }
    }
    res = ModelResponseAdapter.normalize_model_response(raw_kimi)
    data = res["normalized_data"]

    # Explicit 0.0 preserved as 0.0
    assert data["shipping_charges"] == 0.0
    assert data["other_charges"] == 0.0
    assert data["adjustment"] == 0.0
    assert data["round_off"] == 0.0
