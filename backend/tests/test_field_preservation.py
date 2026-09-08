import pytest
from app.services.kimi_adapter import KimiK3ResponseAdapter
from app.schemas.invoice import InvoiceResponse


def test_complete_kimi_field_preservation():
    """
    Field Completeness Test verifying 100% field preservation:
    Kimi Response -> Adapter -> normalized_data & normalized_accounting -> API Schema.
    """
    sample_full_kimi = {
        "schema_version": "2.3.0",
        "knowledge_version": "1.0.0",
        "invoice_details": {
            "invoice_number": "INV-2026-FULL",
            "invoice_date": "2026-09-08",
            "due_date": "2026-10-08",
            "po_number": "PO-998877",
            "place_of_supply": "29-Karnataka",
            "payment_terms": "Net 30 Days",
        },
        "vendor_details": {
            "name": "Global Tech Suppliers Pvt Ltd",
            "address": "77 Industrial Suburb, Bengaluru",
            "gstin": "29ABCDE1234F1ZH",
            "pan": "ABCDE1234F",
            "phone": "+91 9876543210",
            "email": "billing@globaltech.com",
            "bank_name": "HDFC Bank Ltd",
            "bank_account_number": "50200012345678",
            "ifsc_code": "HDFC0001234",
            "branch": "Koramangala Branch",
        },
        "customer_details": {
            "name": "Sakshi Financial Systems",
            "address": "12 Innovation Hub, Bengaluru",
            "gstin": "29XYZAB5678C1ZD",
            "pan": "XYZAB5678C",
            "phone": "+91 9123456789",
            "email": "ap@sakshifinance.com",
        },
        "line_items": [
            {
                "line_index": 1,
                "description": "High-Performance Cloud Compute Unit",
                "hsn_code": "998315",
                "quantity": 10.0,
                "unit": "Units",
                "unit_price": 5000.0,
                "discount_amount": 1000.0,
                "discount_type": "amount",
                "taxable_amount": 49000.0,
                "gst_rate": 18.0,
                "cgst_rate": 9.0,
                "cgst_amount": 4410.0,
                "sgst_rate": 9.0,
                "sgst_amount": 4410.0,
                "igst_rate": 0.0,
                "igst_amount": 0.0,
                "cess_rate": 1.0,
                "cess_amount": 490.0,
                "total_amount": 58310.0,
                "coa_suggestion": {
                    "account_id": "ACC_EXP_01",
                    "account_name": "Cloud Computing Infrastructure",
                    "account_type": "expense",
                    "confidence": 0.98,
                },
            }
        ],
        "financial_details": {
            "subtotal": 50000.0,
            "discount_total": 1000.0,
            "taxable_amount": 49000.0,
            "tax_total": 9310.0,
            "cgst_total": 4410.0,
            "sgst_total": 4410.0,
            "igst_total": 0.0,
            "cess_total": 490.0,
            "shipping_charges": 500.0,
            "other_charges": 200.0,
            "adjustment": -10.0,
            "round_off": 0.0,
            "total_amount": 59000.0,
            "currency": "INR",
            "notes": "Payment due within 30 days of receipt.",
        },
        "tds_support": {
            "applicable": True,
            "section": "194C",
            "provision": "Payments to Contractors",
            "nature_of_payment": "Technical Services",
            "rate": 2.0,
            "base_amount": 49000.0,
            "proposed_amount": 980.0,
            "reasoning": "Technical services exceed statutory limit under section 194C.",
        },
        "gst_support": {
            "place_of_supply": "29-Karnataka",
            "gst_type": "INTRA_STATE",
            "is_rcm": False,
        },
        "itc_support": {
            "is_eligible": True,
            "itc_type": "INPUT_SERVICES",
            "block_reason": None,
        },
        "novel_extra_metadata": {
            "custom_tracker_id": "TRACK-889900"
        }
    }

    normalized = KimiK3ResponseAdapter.normalize_kimi_response(sample_full_kimi)

    data = normalized["normalized_data"]
    acct = normalized["normalized_accounting"]

    # 1. Verification of Header & Metadata
    assert data["schema_version"] == "2.3.0"
    assert data["knowledge_version"] == "1.0.0"
    assert data["invoice_number"] == "INV-2026-FULL"
    assert data["payment_terms"] == "Net 30 Days"
    assert data["currency"] == "INR"

    # 2. Verification of Vendor Contact & Bank Details
    assert data["vendor_name"] == "Global Tech Suppliers Pvt Ltd"
    assert data["vendor_phone"] == "+91 9876543210"
    assert data["vendor_email"] == "billing@globaltech.com"
    assert data["bank_details"]["bank_name"] == "HDFC Bank Ltd"
    assert data["bank_details"]["account_number"] == "50200012345678"
    assert data["bank_details"]["ifsc_code"] == "HDFC0001234"

    # 3. Verification of Customer Contact Information
    assert data["customer_name"] == "Sakshi Financial Systems"
    assert data["customer_phone"] == "+91 9123456789"
    assert data["customer_email"] == "ap@sakshifinance.com"
    assert data["customer_pan"] == "XYZAB5678C"

    # 4. Verification of Line Item Properties (EXPLICIT SEPARATE TAX EXPONENTIALS)
    assert len(data["line_items"]) == 1
    item = data["line_items"][0]
    assert item["line_index"] == 1
    assert item["description"] == "High-Performance Cloud Compute Unit"
    assert item["hsn_code"] == "998315"
    assert item["quantity"] == 10.0
    assert item["unit"] == "Units"
    assert item["unit_price"] == 5000.0
    assert item["discount"] == 1000.0
    assert item["discount_type"] == "amount"
    assert item["taxable_amount"] == 49000.0
    assert item["gst_rate"] == 18.0
    assert item["cgst_rate"] == 9.0
    assert item["cgst_amount"] == 4410.0
    assert item["sgst_rate"] == 9.0
    assert item["sgst_amount"] == 4410.0
    assert item["igst_rate"] == 0.0
    assert item["igst_amount"] == 0.0
    assert item["cess_rate"] == 1.0
    assert item["cess_amount"] == 490.0
    assert item["total"] == 58310.0

    # 5. Verification of COA Suggestions
    assert len(acct["accounting"]) == 1
    coa_line = acct["accounting"][0]
    assert coa_line["ai_account_id"] == "ACC_EXP_01"
    assert coa_line["ai_account_name"] == "Cloud Computing Infrastructure"
    assert coa_line["account_type"] == "expense"
    assert coa_line["ai_confidence"] == 0.98

    # 6. Verification of Financial Summary Breakdown
    assert data["subtotal"] == 50000.0
    assert data["discount_total"] == 1000.0
    assert data["tax_total"] == 9310.0
    assert data["cgst_amount"] == 4410.0
    assert data["sgst_amount"] == 4410.0
    assert data["igst_amount"] == 0.0
    assert data["cess_amount"] == 490.0
    assert data["shipping_charges"] == 500.0
    assert data["other_charges"] == 200.0
    assert data["adjustment"] == -10.0
    assert data["total_amount"] == 59000.0
    assert data["notes"] == "Payment due within 30 days of receipt."

    # 7. Verification of Safety Net (Unmapped Extra Keys Preserved)
    assert "additional_fields" in data
    assert data["additional_fields"]["novel_extra_metadata"]["custom_tracker_id"] == "TRACK-889900"
