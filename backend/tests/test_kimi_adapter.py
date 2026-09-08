import pytest
from app.services.kimi_adapter import KimiK3ResponseAdapter


def test_kimi_adapter_normalization():
    sample_kimi = {
        "schema_version": "2.3.0",
        "invoice_details": {
            "invoice_number": "INV-999",
            "invoice_date": "2026-09-08",
            "due_date": "2026-10-08",
            "po_number": "PO-12345",
            "place_of_supply": "29-Karnataka",
            "payment_terms": "30 Days",
        },
        "vendor_details": {
            "name": "Acme Traders",
            "address": "123 Business Park, Bengaluru",
            "gstin": "29ABCDE1234F1ZH",
            "pan": "",
            "phone": "9876543210",
            "email": "vendor@acme.com",
        },
        "customer_details": {
            "name": "Sakshi AI Corp",
            "address": "456 Tech Park, Bengaluru",
            "gstin": "29XYZAB5678C1ZD",
            "pan": "",
        },
        "line_items": [
            {
                "description": "Cloud Hosting Services",
                "hsn_code": "998313",
                "quantity": 2,
                "unit_price": 5000,
                "discount_amount": 500,
                "discount_type": "amount",
                "taxable_amount": 9500,
                "cgst_rate": 9,
                "cgst_amount": 855,
                "sgst_rate": 9,
                "sgst_amount": 855,
                "total_amount": 11210,
                "coa_suggestion": {
                    "account_id": "ACC_1",
                    "account_name": "Cloud Hosting & Infrastructure",
                    "account_type": "expense",
                    "confidence": 0.95,
                },
            }
        ],
        "financial_details": {
            "subtotal": 9500,
            "discount_total": 500,
            "tax_total": 1710,
            "cgst_total": 855,
            "sgst_total": 855,
            "total_amount": 11210,
            "currency": "INR",
        },
        "tds_support": {
            "applicable": True,
            "section": "194C",
            "provision": "Payment to Contractors",
            "nature_of_payment": "Technical Services",
            "rate": 2.0,
            "proposed_amount": 190.0,
        },
    }

    mock_user_coa = [
        {
            "account_id": "ACC_1",
            "account_name": "Cloud Hosting & Infrastructure",
            "account_type": "expense",
        }
    ]

    normalized = KimiK3ResponseAdapter.normalize_kimi_response(sample_kimi, mock_user_coa)

    data = normalized["normalized_data"]
    acct = normalized["normalized_accounting"]

    assert data["invoice_number"] == "INV-999"
    assert data["vendor_name"] == "Acme Traders"
    assert data["vendor_gstin"] == "29ABCDE1234F1ZH"
    assert data["vendor_pan"] == "ABCDE1234F"  # Auto-derived from GSTIN
    assert data["customer_pan"] == "XYZAB5678C"  # Auto-derived from GSTIN

    assert len(data["line_items"]) == 1
    assert data["line_items"][0]["description"] == "Cloud Hosting Services"
    assert data["line_items"][0]["taxable_amount"] == 9500.0
    assert data["subtotal"] == 9500.0
    assert data["total_amount"] == 11210.0

    assert len(acct["accounting"]) == 1
    assert acct["accounting"][0]["match_status"] == "EXACT_MATCH"
    assert acct["accounting"][0]["account_id"] == "ACC_1"

    assert acct["tds_assessment"]["applicable"] is True
    assert acct["tds_assessment"]["section"] == "194C"
    assert acct["tds_assessment"]["rate"] == 2.0
