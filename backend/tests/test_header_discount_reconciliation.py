import pytest
from decimal import Decimal
from typing import Dict, Any

from app.services.financial_validator import FinancialValidator


@pytest.fixture
def validator():
    return FinancialValidator(tolerance=1.0)


# ==============================================================================
# MOST IMPORTANT TESTS SPECIFIED IN THE PROMPT
# ==============================================================================

def test_critical_a_summary_header_discount_passes(validator):
    """
    Line gross = 1000, Line discount = 100, Line taxable = 900
    Header discount = 100, Subtotal = 900, Tax = 162
    A) Printed total = 1062
    Expected: PASS (Header discount recognized as summary; not deducted twice).
    """
    invoice_data = {
        "subtotal": 900.0,
        "discount_total": 100.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 10,
                "unit_price": 100.0,
                "discount": "10%",
                "taxable_amount": 900.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["status"] == "PASSED"
    assert check4["discount_treatment"] == "SUMMARY_HEADER_DISCOUNT"
    assert check4["calculated_value"] == 1062.0


def test_critical_b_duplicate_deduction_requires_review(validator):
    """
    Line gross = 1000, Line discount = 100, Line taxable = 900
    Header discount = 100, Subtotal = 900, Tax = 162
    B) Printed total = 962
    Expected: REVIEW_REQUIRED (NOT PASS).
    Because the same ₹100 could be a duplicate summary deduction OR a legitimate second ₹100 discount.
    """
    invoice_data = {
        "subtotal": 900.0,
        "discount_total": 100.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 962.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 10,
                "unit_price": 100.0,
                "discount": "10%",
                "taxable_amount": 900.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["status"] == "REVIEW_REQUIRED"
    assert check4.get("issue") == "AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION"


def test_critical_missing_subtotal_requires_review(validator):
    """
    Gross = 1000, Line discount = 100, Header discount = 100, Tax = 162
    Printed total = 1062, Subtotal = missing
    Expected: REVIEW_REQUIRED (Do not guess whether subtotal was gross or net).
    """
    invoice_data = {
        "discount_total": 100.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 10,
                "unit_price": 100.0,
                "discount": "10%",
                "taxable_amount": 900.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["status"] == "REVIEW_REQUIRED"
    assert check4.get("issue") == "AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION"


def test_critical_small_discount_collision_requires_review(validator):
    """
    D_header = ₹0.50 (<= ₹1.00 tolerance).
    Both summary (1000 + 180 = 1180) and additional (1000 - 0.50 + 180 = 1179.50)
    match printed total 1180 within tolerance.
    Expected: REVIEW_REQUIRED (Do NOT select one automatically).
    """
    invoice_data = {
        "subtotal": 1000.0,
        "discount_total": 0.50,
        "tax_total": 180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "total_amount": 1180.0,
        "line_items": [
            {
                "description": "Item with 10 line discount",
                "quantity": 10,
                "unit_price": 101.0,
                "discount": "₹10",
                "taxable_amount": 1000.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["status"] == "REVIEW_REQUIRED"
    assert check4.get("issue") == "AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION"


# ==============================================================================
# 20 EXHAUSTIVE HEADER DISCOUNT REGRESSION SCENARIOS
# ==============================================================================

def test_1_line_discount_only(validator):
    """1. Line discount only: G=1000, D_lines=100, T=900, D_header=0, Tax=162 -> Total=1062"""
    inv = {
        "subtotal": 900.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["discount_treatment"] == "LINE_DISCOUNTS_ONLY"


def test_2_header_discount_only(validator):
    """2. Header discount only: G=1000, D_lines=0, Subtotal=1000, D_header=100, Tax=162 -> Total=1062"""
    inv = {
        "subtotal": 1000.0,
        "discount_total": 100.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "taxable_amount": 1000.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["discount_treatment"] == "SOLE_HEADER_DISCOUNT"


def test_3_line_plus_summary_header_discount(validator):
    """3. Line + summary header discount: G=1000, D_l=100, T=900, Subtotal=900, D_h=100, Tax=162 -> Total=1062"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 100.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "₹100", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["discount_treatment"] == "SUMMARY_HEADER_DISCOUNT"


def test_4_line_plus_additional_header_discount(validator):
    """4. Line + additional header discount: G=1000, D_l=100, T=900, Subtotal=900, D_h=50, Tax=153 -> Total=1003"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 50.0,
        "tax_total": 153.0,
        "cgst_amount": 76.5,
        "sgst_amount": 76.5,
        "total_amount": 1003.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["discount_treatment"] == "ADDITIONAL_HEADER_DISCOUNT"


def test_5_gross_subtotal_plus_header_discount(validator):
    """5. Gross subtotal + header discount: G=1000, D_l=100, Subtotal=1000 (gross), D_h=100, Tax=162 -> Total=1062"""
    inv = {
        "subtotal": 1000.0,
        "discount_total": 100.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check2 = next(c for c in res["checks"] if c["name"] == "line_item_sum_vs_subtotal")
    assert check2["status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["discount_treatment"] == "GROSS_SUBTOTAL_HEADER_DEDUCTION"


def test_6_missing_subtotal_with_concurrent_discounts(validator):
    """6. Missing subtotal with both line and header discounts -> REVIEW_REQUIRED"""
    inv = {
        "discount_total": 50.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1012.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["status"] == "REVIEW_REQUIRED"


def test_7_d_header_equals_d_lines_duplicate_deduction(validator):
    """7. D_header == D_lines + duplicate deduction in total -> REVIEW_REQUIRED"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 100.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 962.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"


def test_8_d_header_less_than_d_lines_unmatched(validator):
    """8. D_header < D_lines and total does not match additional deduction -> REVIEW_REQUIRED"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 50.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,  # Total did not deduct the 50!
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"


def test_9_d_header_greater_than_d_lines_unmatched(validator):
    """9. D_header > D_lines and total does not match additional deduction -> REVIEW_REQUIRED"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 200.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,  # Total ignored the 200 discount!
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"


def test_10_d_header_less_than_1_inr_collision(validator):
    """10. D_header <= ₹1 collision -> REVIEW_REQUIRED"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 0.75,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"


def test_11_d_header_exactly_1_inr_collision(validator):
    """11. D_header exactly ₹1.00 collision -> REVIEW_REQUIRED"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 1.00,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"


def test_12_paise_rounding_reconciliation(validator):
    """12. Paise rounding: line discount sums to 99.99, header discount is 100.00 (diff 0.01 <= 1.0)"""
    inv = {
        "subtotal": 900.01,
        "discount_total": 100.00,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.01,
        "line_items": [
            {"quantity": 1, "unit_price": 333.33, "discount": "₹33.33", "taxable_amount": 300.00},
            {"quantity": 1, "unit_price": 333.33, "discount": "₹33.33", "taxable_amount": 300.00},
            {"quantity": 1, "unit_price": 333.34, "discount": "₹33.33", "taxable_amount": 300.01},
        ],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["discount_treatment"] == "SUMMARY_HEADER_DISCOUNT"


def test_13_shipping_with_header_discount(validator):
    """13. Shipping charges with additional header discount"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 50.0,
        "tax_total": 153.0,
        "shipping_charges": 100.0,
        "total_amount": 1103.0,  # 900 - 50 + 153 + 100 = 1103
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"


def test_14_roundoff_with_summary_discount(validator):
    """14. Round-off adjustment with summary header discount"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 100.0,
        "tax_total": 162.0,
        "round_off": 0.25,
        "total_amount": 1062.25,  # 900 + 162 + 0.25 = 1062.25
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check5 = next(c for c in res["checks"] if c["name"] == "round_off_consistency")
    assert check5["status"] == "PASSED"


def test_15_multi_line_summary_reconciliation(validator):
    """15. Multi-line items: L1 (1000 - 100 = 900), L2 (500 - 50 = 450), Subtotal=1350, D_h=150, Tax=243 -> Total=1593"""
    inv = {
        "subtotal": 1350.0,
        "discount_total": 150.0,
        "tax_total": 243.0,
        "cgst_amount": 121.5,
        "sgst_amount": 121.5,
        "total_amount": 1593.0,
        "line_items": [
            {"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0},
            {"quantity": 5, "unit_price": 100.0, "discount": "10%", "taxable_amount": 450.0},
        ],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["discount_treatment"] == "SUMMARY_HEADER_DISCOUNT"


def test_16_multi_line_additional_reconciliation(validator):
    """16. Multi-line items with additional header discount: Subtotal=1350, D_h=100 (extra), Tax=225 -> Total=1475"""
    inv = {
        "subtotal": 1350.0,
        "discount_total": 100.0,
        "tax_total": 225.0,
        "cgst_amount": 112.5,
        "sgst_amount": 112.5,
        "total_amount": 1475.0,  # 1350 - 100 + 225 = 1475
        "line_items": [
            {"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0},
            {"quantity": 5, "unit_price": 100.0, "discount": "10%", "taxable_amount": 450.0},
        ],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["discount_treatment"] == "ADDITIONAL_HEADER_DISCOUNT"


def test_17_invalid_grand_total_mismatch(validator):
    """17. Invalid grand total produces MISMATCH"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 100.0,
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 9999.0,  # Corrupted total
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"


def test_18_invalid_subtotal_mismatch(validator):
    """18. Subtotal does not match either gross or net -> MISMATCH"""
    inv = {
        "subtotal": 5555.0,  # Corrupted subtotal
        "tax_total": 162.0,
        "total_amount": 1062.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    assert any("Subtotal mismatch" in err for err in res["errors"])


def test_19_alias_discount_field_resolution(validator):
    """19. Header discount passed as 'discount' instead of 'discount_total'"""
    inv = {
        "subtotal": 900.0,
        "discount": 100.0,  # Alias
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    check4 = next(c for c in res["checks"] if c["name"] == "extracted_total_vs_calculated_total")
    assert check4["discount_treatment"] == "SUMMARY_HEADER_DISCOUNT"


def test_20_ambiguous_cases_must_remain_review_required(validator):
    """20. Ambiguous discount cases must always set overall_status = REVIEW_REQUIRED, never PASSED"""
    inv = {
        "subtotal": 900.0,
        "discount_total": 75.0,  # Unexplained discount: line discount was 100, header says 75
        "tax_total": 162.0,
        "cgst_amount": 81.0,
        "sgst_amount": 81.0,
        "total_amount": 1062.0,
        "line_items": [{"quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    assert any("AMBIGUOUS_HEADER_DISCOUNT_RECONCILIATION" in w for w in res["warnings"])
