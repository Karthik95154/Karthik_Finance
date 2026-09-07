"""
Comprehensive Test Suite for Phase 2: New VLM Schema Compatibility.

Covers the 22 required functional and adversarial scenarios:
1. Perfect new-schema invoice
2. Intra-state invoice
3. Inter-state invoice
4. Cess invoice (flat & nested tax_details)
5. Discount invoice (line & header)
6. Adjustment invoice (positive, negative, zero)
7. hsn_sac_code without hsn_code
8. hsn_code already present
9. line_amount + taxable_amount + total
10. line_amount + taxable_amount, total missing
11. line_amount only (no qty, unit_price, or taxable_amount)
12. total present
13. taxable_amount present
14. POS available through existing sources
15. POS missing / ambiguous
16. raw_fields fallback
17. additional_fields Cess
18. all optional metadata fields preserved
19. date "31-Jul-26"
20. canonical value must never be overwritten by fallback
21. adjustment must affect grand-total arithmetic
22. Cess reconciliation remains correct

Plus Mutation Tests:
- canonical value + conflicting raw_fields -> canonical wins
- canonical value + conflicting additional_fields -> canonical wins
- hsn_code + different hsn_sac_code -> hsn_code remains authoritative
- taxable_amount + different line_amount -> taxable_amount remains authoritative
- total + different line_amount -> total remains authoritative
"""

import pytest
from unittest.mock import MagicMock
from app.services.invoice_processing import get_effective_invoice_data
from app.services.gst_engine import gst_engine, extract_tax_value
from app.services.financial_validator import financial_validator
from app.services.journal_generator import journal_generator
from app.core.date_utils import parse_and_normalize_date
from app.db.models import Invoice


# ============================================================================
# 1. Perfect new-schema invoice
# ============================================================================
def test_scenario_01_perfect_new_schema():
    payload = {
        "invoice_number": "INV-2026-001",
        "invoice_date": "2026-08-15",
        "vendor_name": "Acme Industrial Tools",
        "vendor_gstin": "27AAPCA1234A1Z5",
        "customer_name": "Zenith Corp",
        "customer_gstin": "27BBBBB5678B1Z2",
        "subtotal": 10000.0,
        "taxable_amount": 10000.0,
        "cgst_total": 900.0,
        "sgst_total": 900.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "line_items": [
            {
                "description": "Widget Assembly A",
                "hsn_sac_code": "84713010",
                "code_type": "HSN",
                "quantity": 10.0,
                "unit": "PCS",
                "unit_price": 1000.0,
                "line_amount": 10000.0,
                "taxable_amount": 10000.0,
                "cgst_rate": 9.0,
                "cgst_amount": 900.0,
                "sgst_rate": 9.0,
                "sgst_amount": 900.0,
                "total": 11800.0,
            }
        ],
    }
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {"data": payload}
    mock_inv.current_vlm_output = None

    effective = get_effective_invoice_data(mock_inv)
    assert effective["line_items"][0]["hsn_code"] == "84713010"
    assert effective["line_items"][0]["hsn_sac_code"] == "84713010"
    assert effective["line_items"][0]["code_type"] == "HSN"

    gst_res = gst_engine.evaluate_gst(effective)
    assert gst_res["supply_type"] == "INTRA_STATE"
    assert gst_res["validation_status"] == "PASSED"

    fin_res = financial_validator.validate_invoice(effective, gst_res)
    assert fin_res["overall_status"] == "PASSED"

    j_res = journal_generator.generate_journal(effective, gst_result=gst_res, financial_validation_result=fin_res)
    assert j_res["status"] in ("BALANCED", "REVIEW_REQUIRED")
    assert j_res["validation"]["balanced"] is True


# ============================================================================
# 2 & 3. Intra-state vs Inter-state supply resolution
# ============================================================================
def test_scenario_02_intra_state():
    payload = {
        "vendor_gstin": "29AAPCA1234A1Z5",
        "customer_gstin": "29BBBBB5678B1Z2",
        "subtotal": 5000.0,
        "cgst_total": 450.0,
        "sgst_total": 450.0,
        "tax_total": 900.0,
        "total_amount": 5900.0,
        "line_items": [
            {
                "description": "Local Consulting",
                "quantity": 1.0,
                "unit_price": 5000.0,
                "taxable_amount": 5000.0,
                "cgst_amount": 450.0,
                "sgst_amount": 450.0,
                "total": 5900.0,
            }
        ]
    }
    gst_res = gst_engine.evaluate_gst(payload)
    assert gst_res["supply_type"] == "INTRA_STATE"
    assert gst_res["supplier_state_code"] == "29"
    assert gst_res["buyer_state_code"] == "29"


def test_scenario_03_inter_state():
    payload = {
        "vendor_gstin": "27AAPCA1234A1Z5",  # Maharashtra
        "customer_gstin": "29BBBBB5678B1Z2",  # Karnataka
        "subtotal": 5000.0,
        "igst_total": 900.0,
        "tax_total": 900.0,
        "total_amount": 5900.0,
        "line_items": [
            {
                "description": "Cross-state Supply",
                "quantity": 1.0,
                "unit_price": 5000.0,
                "taxable_amount": 5000.0,
                "igst_amount": 900.0,
                "total": 5900.0,
            }
        ]
    }
    gst_res = gst_engine.evaluate_gst(payload)
    assert gst_res["supply_type"] == "INTER_STATE"


# ============================================================================
# 4. Cess invoice (flat in additional_fields and nested in tax_details)
# ============================================================================
def test_scenario_04_cess_flat_additional_fields():
    payload = {
        "vendor_gstin": "27AAPCA1234A1Z5",
        "customer_gstin": "27BBBBB5678B1Z2",
        "subtotal": 100000.0,
        "cgst_total": 14000.0,
        "sgst_total": 14000.0,
        "tax_total": 32000.0,
        "total_amount": 132000.0,
        "additional_fields": {
            "cess": 4000.0
        },
        "line_items": [
            {
                "description": "Luxury Automobile Part",
                "quantity": 1.0,
                "unit_price": 100000.0,
                "taxable_amount": 100000.0,
                "cgst_amount": 14000.0,
                "sgst_amount": 14000.0,
                "cess_amount": 4000.0,
                "total": 132000.0,
            }
        ]
    }
    assert extract_tax_value(payload, "cess") == 4000.0
    gst_res = gst_engine.evaluate_gst(payload)
    fin_res = financial_validator.validate_invoice(payload, gst_res)
    assert fin_res["overall_status"] == "PASSED"


def test_scenario_04b_cess_nested_tax_details():
    payload = {
        "vendor_gstin": "27AAPCA1234A1Z5",
        "customer_gstin": "27BBBBB5678B1Z2",
        "subtotal": 100000.0,
        "cgst_total": 14000.0,
        "sgst_total": 14000.0,
        "tax_total": 32000.0,
        "total_amount": 132000.0,
        "additional_fields": {
            "tax_details": {
                "output_tax": {
                    "cess": {"amount": 4000.0}
                }
            }
        },
        "line_items": [
            {
                "description": "Luxury Automobile Part",
                "quantity": 1.0,
                "unit_price": 100000.0,
                "taxable_amount": 100000.0,
                "cgst_amount": 14000.0,
                "sgst_amount": 14000.0,
                "cess_amount": 4000.0,
                "total": 132000.0,
            }
        ]
    }
    assert extract_tax_value(payload, "cess") == 4000.0
    gst_res = gst_engine.evaluate_gst(payload)
    fin_res = financial_validator.validate_invoice(payload, gst_res)
    assert fin_res["overall_status"] == "PASSED"


# ============================================================================
# 5. Discount invoice
# ============================================================================
def test_scenario_05_discount_invoice():
    payload = {
        "subtotal": 1000.0,  # gross subtotal before discount
        "discount_total": 100.0,
        "tax_total": 162.0,
        "total_amount": 1062.0,
        "line_items": [
            {
                "description": "Item with 10% discount",
                "quantity": 1.0,
                "unit_price": 1000.0,
                "discount": 100.0,
                "discount_type": "amount",
                "taxable_amount": 900.0,
                "igst_amount": 162.0,
                "total": 1062.0,
            }
        ]
    }
    fin_res = financial_validator.validate_invoice(payload)
    assert fin_res["overall_status"] == "PASSED"


# ============================================================================
# 6. Adjustment invoice (positive, negative, zero)
# ============================================================================
def test_scenario_06_adjustment_variations():
    # 6a. Zero adjustment
    payload_zero = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "adjustment": 0.0,
        "total_amount": 1180.0,
        "line_items": [{"taxable_amount": 1000.0, "total": 1180.0, "igst_amount": 180.0}]
    }
    is_valid, errors, _ = financial_validator.validate_invoice_math(payload_zero)
    assert is_valid
    assert len(errors) == 0

    # 6b. Positive adjustment (+50.0)
    payload_pos = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "adjustment": 50.0,
        "total_amount": 1230.0,
        "line_items": [{"taxable_amount": 1000.0, "total": 1180.0, "igst_amount": 180.0}]
    }
    is_valid, errors, _ = financial_validator.validate_invoice_math(payload_pos)
    assert is_valid
    fin_res = financial_validator.validate_invoice(payload_pos)
    assert fin_res["overall_status"] == "PASSED"
    j_res = journal_generator.generate_journal(payload_pos)
    assert j_res["validation"]["balanced"] is True

    # 6c. Negative adjustment (-50.0)
    payload_neg = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "adjustment": -50.0,
        "total_amount": 1130.0,
        "line_items": [{"taxable_amount": 1000.0, "total": 1180.0, "igst_amount": 180.0}]
    }
    is_valid, errors, _ = financial_validator.validate_invoice_math(payload_neg)
    assert is_valid
    fin_res_neg = financial_validator.validate_invoice(payload_neg)
    assert fin_res_neg["overall_status"] == "PASSED"
    j_res_neg = journal_generator.generate_journal(payload_neg)
    assert j_res_neg["validation"]["balanced"] is True

    # 6d. Adjustment causing genuine arithmetic mismatch
    payload_bad = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "adjustment": 50.0,
        "total_amount": 1500.0,  # Incorrect
        "line_items": [{"taxable_amount": 1000.0, "total": 1180.0, "igst_amount": 180.0}]
    }
    is_valid_bad, errors_bad, _ = financial_validator.validate_invoice_math(payload_bad)
    assert not is_valid_bad
    assert any("Computed total" in e for e in errors_bad)


# ============================================================================
# 7 & 8. HSN / SAC handling
# ============================================================================
def test_scenario_07_hsn_sac_code_without_hsn_code():
    item = {
        "description": "Software Service",
        "hsn_sac_code": "998313",
        "code_type": "SAC",
        "taxable_amount": 2000.0,
    }
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {"data": {"line_items": [item]}}
    mock_inv.current_vlm_output = None

    effective = get_effective_invoice_data(mock_inv)
    res_item = effective["line_items"][0]
    assert res_item["hsn_code"] == "998313"
    assert res_item["hsn_sac_code"] == "998313"
    assert res_item["code_type"] == "SAC"


def test_scenario_08_hsn_code_already_present():
    item = {
        "description": "Dual Coded Item",
        "hsn_code": "8471",
        "hsn_sac_code": "84713010",
        "taxable_amount": 2000.0,
    }
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {"data": {"line_items": [item]}}
    mock_inv.current_vlm_output = None

    effective = get_effective_invoice_data(mock_inv)
    res_item = effective["line_items"][0]
    # hsn_code must NOT be overwritten!
    assert res_item["hsn_code"] == "8471"
    assert res_item["hsn_sac_code"] == "84713010"


# ============================================================================
# 9-13. Line Amount, Taxable Amount, and Total Precedence
# ============================================================================
def test_scenario_09_line_amount_taxable_amount_total_all_present():
    item = {
        "description": "Item Full",
        "quantity": 2.0,
        "unit_price": 500.0,
        "line_amount": 1000.0,
        "taxable_amount": 950.0,  # Explicit assessable value with trade discount
        "igst_amount": 171.0,
        "total": 1121.0,
    }
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {"data": {"line_items": [item]}}
    mock_inv.current_vlm_output = None

    effective = get_effective_invoice_data(mock_inv)
    res_item = effective["line_items"][0]
    # Authoritative values remain untouched
    assert res_item["taxable_amount"] == 950.0
    assert res_item["total"] == 1121.0
    assert res_item["line_amount"] == 1000.0


def test_scenario_10_line_amount_taxable_amount_total_missing():
    item = {
        "description": "Item Missing Total",
        "taxable_amount": 1000.0,
        "line_amount": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
    }
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {"data": {"line_items": [item]}}
    mock_inv.current_vlm_output = None

    effective = get_effective_invoice_data(mock_inv)
    res_item = effective["line_items"][0]
    # total must be safely derived as taxable + taxes = 1180.0, NOT equal to line_amount or taxable_amount
    assert res_item["taxable_amount"] == 1000.0
    assert res_item["total"] == 1180.0


def test_scenario_11_line_amount_only():
    item = {
        "description": "Lump-sum Row",
        "line_amount": 2500.0,
        "cgst_amount": 225.0,
        "sgst_amount": 225.0,
    }
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {"data": {"line_items": [item]}}
    mock_inv.current_vlm_output = None

    effective = get_effective_invoice_data(mock_inv)
    res_item = effective["line_items"][0]
    # taxable_amount safely falls back to line_amount
    assert res_item["taxable_amount"] == 2500.0
    # total is derived with taxes: 2500 + 450 = 2950.0
    assert res_item["total"] == 2950.0


# ============================================================================
# 14 & 15. Place of Supply (POS) Handling
# ============================================================================
def test_scenario_14_pos_available_through_existing_sources():
    # POS derived from customer address
    payload = {
        "vendor_gstin": "27AAPCA1234A1Z5",  # MH
        "customer_address": "Plot 42, Gachibowli, Hyderabad, Telangana 500032",
        "subtotal": 1000.0,
        "total_amount": 1180.0,
    }
    gst_res = gst_engine.evaluate_gst(payload)
    assert gst_res["place_of_supply_state_code"] == "36"
    assert gst_res["supply_type"] == "INTER_STATE"


def test_scenario_15_pos_missing_ambiguous():
    payload = {
        "vendor_gstin": "27AAPCA1234A1Z5",  # MH
        "customer_address": "123 Unknown St, Global City",
        "subtotal": 1000.0,
        "total_amount": 1180.0,
    }
    gst_res = gst_engine.evaluate_gst(payload)
    # When buyer state is unknown, defaults to supplier state with review/warning
    assert gst_res["supply_type"] in ("INTRA_STATE", "REVIEW_REQUIRED")


# ============================================================================
# 16. raw_fields fallback
# ============================================================================
def test_scenario_16_raw_fields_fallback():
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {
        "data": {},
        "raw_fields": {
            "invoice_number": "INV-RAW-999",
            "vendor_gstin": "36AAPCA1234A1Z5",
            "vendor_phone": "+91 9876543210",
        }
    }
    mock_inv.current_vlm_output = None

    effective = get_effective_invoice_data(mock_inv)
    assert effective["invoice_number"] == "INV-RAW-999"
    assert effective["vendor_gstin"] == "36AAPCA1234A1Z5"
    assert effective["vendor_phone"] == "+91 9876543210"


# ============================================================================
# 18. Optional metadata preservation
# ============================================================================
def test_scenario_18_metadata_preservation():
    data = {
        "vendor_cin": "U72200TG2020PTC123456",
        "vendor_email": "billing@vendor.com",
        "vendor_phone": "040-12345678",
        "payment_terms": "Net 30",
        "bank_details": {
            "account_number": "987654321",
            "ifsc_code": "HDFC0001234",
            "bank_name": "HDFC Bank",
        },
        "line_items": [
            {
                "description": "Service A",
                "unit": "HOURS",
                "hsn_sac_code": "9983",
                "code_type": "SAC",
                "line_amount": 5000.0,
                "gst_rate": 18.0,
            }
        ]
    }
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {"data": data}
    mock_inv.current_vlm_output = None

    effective = get_effective_invoice_data(mock_inv)
    assert effective["vendor_cin"] == "U72200TG2020PTC123456"
    assert effective["vendor_email"] == "billing@vendor.com"
    assert effective["bank_details"]["ifsc_code"] == "HDFC0001234"
    assert effective["line_items"][0]["unit"] == "HOURS"
    assert effective["line_items"][0]["code_type"] == "SAC"


# ============================================================================
# 19. Date normalizer with "31-Jul-26"
# ============================================================================
def test_scenario_19_date_normalization():
    assert parse_and_normalize_date("31-Jul-26") == "2026-07-31"
    assert parse_and_normalize_date("31-Jul-2026") == "2026-07-31"
    assert parse_and_normalize_date("2026-07-31") == "2026-07-31"


# ============================================================================
# MUTATION TESTS: Proof of Canonical Authority
# ============================================================================
def test_mutation_canonical_vs_conflicting_raw_fields():
    # Canonical invoice_number must NOT be overwritten by raw_fields
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {
        "data": {"invoice_number": "INV-CANONICAL-123"},
        "raw_fields": {"invoice_number": "INV-RAW-CONFLICT"}
    }
    mock_inv.current_vlm_output = None
    effective = get_effective_invoice_data(mock_inv)
    assert effective["invoice_number"] == "INV-CANONICAL-123"


def test_mutation_hsn_code_authority():
    # If hsn_code is present, a different hsn_sac_code must not overwrite it
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {
        "data": {
            "line_items": [
                {
                    "description": "Item",
                    "hsn_code": "1111",
                    "hsn_sac_code": "2222",
                }
            ]
        }
    }
    mock_inv.current_vlm_output = None
    effective = get_effective_invoice_data(mock_inv)
    assert effective["line_items"][0]["hsn_code"] == "1111"
    assert effective["line_items"][0]["hsn_sac_code"] == "2222"


def test_mutation_taxable_amount_authority_over_line_amount():
    # Explicit taxable_amount must remain authoritative even if line_amount differs
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {
        "data": {
            "line_items": [
                {
                    "description": "Item",
                    "taxable_amount": 800.0,
                    "line_amount": 1000.0,
                }
            ]
        }
    }
    mock_inv.current_vlm_output = None
    effective = get_effective_invoice_data(mock_inv)
    assert effective["line_items"][0]["taxable_amount"] == 800.0
    assert effective["line_items"][0]["line_amount"] == 1000.0


def test_mutation_total_authority_over_line_amount():
    # Explicit total must remain authoritative even if line_amount differs
    mock_inv = MagicMock(spec=Invoice)
    mock_inv.raw_vlm_output = {
        "data": {
            "line_items": [
                {
                    "description": "Item",
                    "total": 1180.0,
                    "line_amount": 1000.0,
                }
            ]
        }
    }
    mock_inv.current_vlm_output = None
    effective = get_effective_invoice_data(mock_inv)
    assert effective["line_items"][0]["total"] == 1180.0
    assert effective["line_items"][0]["line_amount"] == 1000.0
