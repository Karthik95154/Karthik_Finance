"""
Focused Test Suite for:
1. Cess Extraction Mapping Fix (backend/app/services/gst_engine.py & financial_validator.py)
2. Header GST <-> Line GST Reconciliation (backend/app/services/financial_validator.py)

Covers all 29 required test specifications.
"""
import pytest
from decimal import Decimal
from typing import Dict, Any

from app.services.financial_validator import FinancialValidator
from app.services.gst_engine import gst_engine, extract_tax_value


@pytest.fixture
def validator():
    return FinancialValidator(tolerance=1.0)


# ==============================================================================
# GROUP A: CESS EXTRACTION MAPPING TESTS (1-10)
# ==============================================================================

def test_1_cess_amount_header_and_line(validator):
    """1. cess_amount header + line -> PASS"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "cess_amount": 120.0,
        "tax_total": 300.0,
        "total_amount": 1300.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["source"]["cess_amount"] == 120.0
    assert res["calculated"]["gst_total"] == 300.0
    assert res["calculated"]["grand_total"] == 1300.0


def test_2_cess_alias(validator):
    """2. 'cess' alias -> PASS"""
    inv = {
        "subtotal": 1000.0,
        "cgst": 90.0,
        "sgst": 90.0,
        "cess": 120.0,
        "tax_total": 300.0,
        "total_amount": 1300.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst": 90.0, "sgst": 90.0, "cess": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["source"]["cess_amount"] == 120.0
    assert res["calculated"]["gst_total"] == 300.0


def test_3_total_cess(validator):
    """3. total_cess alias -> PASS"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "total_cess": 120.0,
        "tax_total": 300.0,
        "total_amount": 1300.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "total_cess": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["source"]["cess_amount"] == 120.0


def test_4_compensation_cess(validator):
    """4. compensation_cess alias -> PASS"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "compensation_cess": 120.0,
        "tax_total": 300.0,
        "total_amount": 1300.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "compensation_cess": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["source"]["cess_amount"] == 120.0


def test_5_compensation_cess_amount(validator):
    """5. compensation_cess_amount alias -> PASS"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "compensation_cess_amount": 120.0,
        "tax_total": 300.0,
        "total_amount": 1300.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "compensation_cess_amount": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["source"]["cess_amount"] == 120.0


def test_6_compensation_cess_with_space(validator):
    """6. 'compensation cess' in additional_fields -> PASS"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 300.0,
        "total_amount": 1300.0,
        "additional_fields": {"Compensation Cess": "120.00"},
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["source"]["cess_amount"] == 120.0


def test_7_cess_explicit_zero(validator):
    """7. Cess = 0.00 explicitly -> PASS (preserved as valid number)"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "cess_amount": 0.0,
        "tax_total": 180.0,
        "total_amount": 1180.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 0.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["source"]["cess_amount"] == 0.0


def test_8_cess_plus_cgst_sgst(validator):
    """8. Cess + CGST + SGST (intra-state with cess) -> PASS"""
    inv = {
        "subtotal": 2000.0,
        "cgst_amount": 180.0,
        "sgst_amount": 180.0,
        "cess_amount": 240.0,
        "tax_total": 600.0,
        "total_amount": 2600.0,
        "line_items": [
            {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 120.0, "total": 1300.0},
            {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 120.0, "total": 1300.0},
        ]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["gst_total"] == 600.0


def test_9_cess_plus_igst(validator):
    """9. Cess + IGST (inter-state with cess) -> PASS"""
    inv = {
        "subtotal": 1000.0,
        "igst_amount": 180.0,
        "cess_amount": 120.0,
        "tax_total": 300.0,
        "total_amount": 1300.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "igst_amount": 180.0, "cess_amount": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["gst_total"] == 300.0


def test_10_wrong_header_cess_vs_line_cess(validator):
    """10. Wrong header Cess vs line Cess (H=150, L=120) -> MISMATCH"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "cess_amount": 150.0,
        "tax_total": 330.0,
        "total_amount": 1330.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "MISMATCH"
    assert any("HEADER_LINE_CESS_MISMATCH" in m for m in recon_chk["mismatches"])


# ==============================================================================
# GROUP B: HEADER <-> LINE GST RECONCILIATION TESTS (11-29)
# ==============================================================================

def test_11_header_and_line_gst_match(validator):
    """11. Header and line GST match perfectly -> PASS"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 180.0,
        "total_amount": 1180.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "PASSED"


def test_12_header_cgst_mismatch(validator):
    """12. Header CGST mismatch: H=100, L=90 -> MISMATCH (HEADER_LINE_CGST_MISMATCH)"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 100.0,
        "sgst_amount": 90.0,
        "tax_total": 190.0,
        "total_amount": 1190.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "MISMATCH"
    assert any("HEADER_LINE_CGST_MISMATCH" in m for m in recon_chk["mismatches"])


def test_13_header_sgst_mismatch(validator):
    """13. Header SGST mismatch: H=100, L=90 -> MISMATCH (HEADER_LINE_SGST_MISMATCH)"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 100.0,
        "tax_total": 190.0,
        "total_amount": 1190.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "MISMATCH"
    assert any("HEADER_LINE_SGST_MISMATCH" in m for m in recon_chk["mismatches"])


def test_14_header_igst_mismatch(validator):
    """14. Header IGST mismatch: H=200, L=180 -> MISMATCH (HEADER_LINE_IGST_MISMATCH)"""
    inv = {
        "subtotal": 1000.0,
        "igst_amount": 200.0,
        "tax_total": 200.0,
        "total_amount": 1200.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "igst_amount": 180.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "MISMATCH"
    assert any("HEADER_LINE_IGST_MISMATCH" in m for m in recon_chk["mismatches"])


def test_15_header_cess_mismatch(validator):
    """15. Header Cess mismatch: H=130, L=120 -> MISMATCH (HEADER_LINE_CESS_MISMATCH)"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "cess_amount": 130.0,
        "tax_total": 310.0,
        "total_amount": 1310.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "MISMATCH"
    assert any("HEADER_LINE_CESS_MISMATCH" in m for m in recon_chk["mismatches"])


def test_16_header_tax_total_mismatch(validator):
    """16. Header tax_total mismatch (line taxes sum 180 vs header tax_total 200) -> MISMATCH"""
    inv = {
        "subtotal": 1000.0,
        "tax_total": 200.0,
        "total_amount": 1200.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "MISMATCH"
    assert any("HEADER_LINE_TAX_TOTAL_MISMATCH" in m for m in recon_chk["mismatches"])


def test_17_component_swap(validator):
    """17. Component swap: Line has CGST=180, SGST=0 while header has CGST=90, SGST=90 -> MISMATCH"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 180.0,
        "total_amount": 1180.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 180.0, "sgst_amount": 0.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "MISMATCH"
    assert any("HEADER_LINE_CGST_MISMATCH" in m for m in recon_chk["mismatches"])
    assert any("HEADER_LINE_SGST_MISMATCH" in m for m in recon_chk["mismatches"])


def test_18_multi_line_corrupted_tax(validator):
    """18. Multi-line corrupted tax: Line 2 CGST is 999 -> MISMATCH (catches Audit Case C5)"""
    inv = {
        "subtotal": 2000.0,
        "cgst_amount": 180.0,
        "sgst_amount": 180.0,
        "tax_total": 360.0,
        "total_amount": 2360.0,
        "line_items": [
            {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0},
            {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 999.0, "sgst_amount": 90.0, "total": 2089.0},
        ]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "MISMATCH"


def test_19_multi_rate_lines(validator):
    """19. Multi-rate lines: Line 1 @ 5%, Line 2 @ 18% matching header sums -> PASS"""
    inv = {
        "subtotal": 2000.0,
        "cgst_amount": 115.0,
        "sgst_amount": 115.0,
        "tax_total": 230.0,
        "total_amount": 2230.0,
        "line_items": [
            {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 25.0, "sgst_amount": 25.0, "total": 1050.0},
            {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0},
        ]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "PASSED"


def test_20_header_only_tax_summary(validator):
    """20. Header-only tax summary: line items omit tax columns -> NOT_APPLICABLE / do NOT force line tax"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 180.0,
        "total_amount": 1180.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "total": None
        }]
    }
    res = validator.validate_invoice(inv)
    # Line total missing triggers LINE_TOTAL_OMITTED_CALCULATED, header tax is valid
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] in ["PASSED", "NOT_APPLICABLE"]


def test_21_line_only_tax(validator):
    """21. Line-only tax: header GST omitted -> valid line-only flow"""
    inv = {
        "subtotal": 1000.0,
        "total_amount": 1180.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["grand_total"] == 1180.0


def test_22_partial_line_tax_breakdown(validator):
    """22. Partial line tax breakdown: 1 of 2 lines has tax, header has tax -> REVIEW_REQUIRED"""
    inv = {
        "subtotal": 2000.0,
        "cgst_amount": 180.0,
        "sgst_amount": 180.0,
        "tax_total": 360.0,
        "total_amount": 2360.0,
        "line_items": [
            {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0},
            {"quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0, "total": 1180.0},
        ]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "REVIEW_REQUIRED"
    assert recon_chk["issue"] == "PARTIAL_LINE_TAX_BREAKDOWN"


def test_23_explicit_zero_tax(validator):
    """23. Explicit zero tax: 0.00 is preserved and matches header 0.00 -> PASS"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 0.0,
        "sgst_amount": 0.0,
        "tax_total": 0.0,
        "total_amount": 1000.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 0.0, "sgst_amount": 0.0, "total": 1000.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "PASSED"


def test_24_diff_0_99_within_tolerance(validator):
    """24. ₹0.99 difference between line sum and header -> PASS (within ₹1.00 tolerance)"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.99,
        "sgst_amount": 90.0,
        "tax_total": 180.99,
        "total_amount": 1180.99,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "PASSED"


def test_25_diff_1_00_boundary(validator):
    """25. ₹1.00 exact difference -> PASS (within tolerance)"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 91.0,
        "sgst_amount": 90.0,
        "tax_total": 181.0,
        "total_amount": 1181.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "PASSED"


def test_26_diff_1_01_outside_tolerance(validator):
    """26. ₹1.01 difference -> MISMATCH (exceeds ₹1.00 tolerance)"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 91.01,
        "sgst_amount": 90.0,
        "tax_total": 181.01,
        "total_amount": 1181.01,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "total": 1180.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    recon_chk = next(c for c in res["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation")
    assert recon_chk["status"] == "MISMATCH"


def test_27_malformed_null_tax_values(validator):
    """27. Malformed/null tax values -> handled gracefully without crashing"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": None,
        "sgst_amount": "invalid_tax",
        "tax_total": 180.0,
        "total_amount": 1180.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": None, "sgst_amount": None, "total": 1000.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] in ["MISMATCH", "REVIEW_REQUIRED"]


def test_28_multiple_aliases_same_value(validator):
    """28. Multiple aliases with same value -> PASS (no duplicate counting)"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "cgst": 90.0,
        "sgst_amount": 90.0,
        "sgst": 90.0,
        "cess_amount": 120.0,
        "total_cess": 120.0,
        "tax_total": 300.0,
        "total_amount": 1300.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0, "cess_amount": 120.0, "total_cess": 120.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["gst_total"] == 300.0


def test_29_multiple_aliases_conflicting_values(validator):
    """29. Multiple aliases with conflicting values -> REVIEW_REQUIRED"""
    inv = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 300.0,
        "total_amount": 1300.0,
        "line_items": [{
            "quantity": 1, "unit_price": 1000.0, "taxable_amount": 1000.0,
            "cgst_amount": 90.0, "sgst_amount": 90.0,
            # Conflicting line Cess aliases
            "cess_amount": 120.0, "total_cess": 150.0, "total": 1300.0
        }]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert any("CONFLICTING_LINE_CESS_ALIASES" in w for w in res["warnings"])
