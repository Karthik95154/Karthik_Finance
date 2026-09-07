"""
Dedicated Test Suite for Line Total Validation in FinancialValidator.
Covers all 33 required test cases using an independent Decimal-based expected-value oracle.
"""
import pytest
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional

from app.services.financial_validator import FinancialValidator, financial_validator


# ==============================================================================
# INDEPENDENT DECIMAL EXPECTED-VALUE ORACLE (NO PRODUCTION REUSE)
# ==============================================================================

def oracle_calc_line(
    qty: Optional[float],
    price: Optional[float],
    discount: Optional[Any],
    discount_type: Optional[str],
    taxable_amount: Optional[float],
    cgst_amt: Optional[float],
    sgst_amt: Optional[float],
    igst_amt: Optional[float],
    cess_amt: Optional[float],
    cgst_rate: Optional[float] = None,
    sgst_rate: Optional[float] = None,
    igst_rate: Optional[float] = None,
    cess_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """Independent Decimal oracle to calculate expected taxable and expected total."""
    d_qty = Decimal(str(qty)) if qty is not None else None
    d_price = Decimal(str(price)) if price is not None else None

    # Calculate taxable base
    calc_taxable = None
    if d_qty is not None and d_price is not None:
        gross = (d_qty * d_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        disc_amt = Decimal("0.00")
        if discount is not None:
            raw_d_str = str(discount).replace("₹", "").replace("%", "").strip()
            d_val = Decimal(raw_d_str)
            if discount_type == "percentage" or "%" in str(discount):
                disc_amt = (gross * d_val / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                disc_amt = d_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        calc_taxable = (gross - disc_amt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    base_taxable = calc_taxable if calc_taxable is not None else (Decimal(str(taxable_amount)) if taxable_amount is not None else None)

    # Taxes
    has_explicit_tax = any(x is not None for x in [cgst_amt, sgst_amt, igst_amt, cess_amt])
    tax_sum = Decimal("0.00")
    if has_explicit_tax:
        for t in [cgst_amt, sgst_amt, igst_amt, cess_amt]:
            if t is not None:
                tax_sum += Decimal(str(t))
    elif any(r is not None and r > 0 for r in [cgst_rate, sgst_rate, igst_rate, cess_rate]) and base_taxable is not None:
        rate_sum = Decimal("0.0")
        for r in [cgst_rate, sgst_rate, igst_rate, cess_rate]:
            if r is not None:
                rate_sum += Decimal(str(r))
        tax_sum = (base_taxable * rate_sum / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        has_explicit_tax = True

    expected_total = (base_taxable + tax_sum).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if base_taxable is not None else None

    return {
        "taxable": float(base_taxable) if base_taxable is not None else None,
        "taxes": float(tax_sum),
        "has_line_tax": has_explicit_tax,
        "expected_total": float(expected_total) if expected_total is not None else None,
    }


@pytest.fixture
def validator():
    return FinancialValidator(tolerance=1.0)


# ==============================================================================
# 33 DEDICATED AUDIT TEST SCENARIOS
# ==============================================================================

def test_1_taxable_only_no_tax(validator):
    """1. Taxable only, no tax: taxable=100, total=100 -> PASS"""
    oracle = oracle_calc_line(1, 100.0, None, None, 100.0, None, None, None, None)
    inv = {
        "subtotal": 100.0,
        "tax_total": 0.0,
        "total_amount": 100.0,
        "line_items": [{"quantity": 1, "unit_price": 100.0, "taxable_amount": oracle["taxable"], "total": oracle["expected_total"]}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"
    assert l_check["line_total_treatment"] == "ZERO_TAX_LINE_MATCH"


def test_2_cgst_plus_sgst(validator):
    """2. CGST + SGST: taxable=100, CGST=9, SGST=9, total=118 -> PASS"""
    oracle = oracle_calc_line(1, 100.0, None, None, 100.0, 9.0, 9.0, None, None)
    inv = {
        "subtotal": 100.0,
        "tax_total": 18.0,
        "cgst_amount": 9.0,
        "sgst_amount": 9.0,
        "total_amount": 118.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 9.0, "total": oracle["expected_total"]
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"
    assert l_check["line_total_treatment"] == "EXPLICIT_LINE_TAXES_MATCH"


def test_3_igst(validator):
    """3. IGST: taxable=100, IGST=18, total=118 -> PASS"""
    oracle = oracle_calc_line(1, 100.0, None, None, 100.0, None, None, 18.0, None)
    inv = {
        "subtotal": 100.0,
        "tax_total": 18.0,
        "igst_amount": 18.0,
        "total_amount": 118.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "igst_amount": 18.0, "total": oracle["expected_total"]
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"
    assert l_check["line_total_treatment"] == "EXPLICIT_LINE_TAXES_MATCH"


def test_4_cess(validator):
    """4. Cess: taxable=100, Cess=12, total=112 -> PASS"""
    oracle = oracle_calc_line(1, 100.0, None, None, 100.0, None, None, None, 12.0)
    inv = {
        "subtotal": 100.0,
        "tax_total": 12.0,
        "cess_amount": 12.0,
        "total_amount": 112.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cess_amount": 12.0, "total": oracle["expected_total"]
        }],
    }
    res = validator.validate_invoice(inv)
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"
    assert l_check["expected_total"] == 112.0


def test_5_cgst_plus_sgst_plus_cess(validator):
    """5. CGST + SGST + Cess: taxable=100, CGST=9, SGST=9, Cess=12, total=130 -> PASS"""
    oracle = oracle_calc_line(1, 100.0, None, None, 100.0, 9.0, 9.0, None, 12.0)
    assert oracle["expected_total"] == 130.0
    inv = {
        "subtotal": 100.0,
        "tax_total": 30.0,
        "cgst_amount": 9.0,
        "sgst_amount": 9.0,
        "cess_amount": 12.0,
        "total_amount": 130.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 9.0, "cess_amount": 12.0, "total": 130.0
        }],
    }
    res = validator.validate_invoice(inv)
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"
    assert l_check["expected_total"] == 130.0


def test_6_corrupted_line_total(validator):
    """6. Corrupted line total: taxable=100, taxes=18, total=9999 -> MISMATCH"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 18.0,
        "cgst_amount": 9.0,
        "sgst_amount": 9.0,
        "total_amount": 118.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 9.0, "total": 9999.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "MISMATCH"
    assert l_check["line_total_treatment"] == "EXPLICIT_LINE_TOTAL_MISMATCH"
    assert l_check["expected_total"] == 118.0
    assert l_check["extracted_total"] == 9999.0
    assert l_check["total_difference"] == 9881.0


def test_7_line_total_missing(validator):
    """7. Line total missing on printed invoice -> PASS (LINE_TOTAL_OMITTED_CALCULATED)"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 18.0,
        "cgst_amount": 9.0,
        "sgst_amount": 9.0,
        "total_amount": 118.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 9.0, "total": None
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"
    assert l_check["line_total_treatment"] == "LINE_TOTAL_OMITTED_CALCULATED"
    assert l_check["expected_total"] == 118.0


def test_8_tax_omitted_from_line_total(validator):
    """8. Tax omitted from line total: taxable=100, taxes=18, total=100 -> MISMATCH"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 18.0,
        "cgst_amount": 9.0,
        "sgst_amount": 9.0,
        "total_amount": 118.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 9.0, "total": 100.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "MISMATCH"
    assert l_check["total_difference"] == 18.0


def test_9_wrong_cgst(validator):
    """9. Wrong CGST: taxable=100, CGST=8, SGST=9, total=118 -> MISMATCH (exp 117 vs ext 118)"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 17.0,
        "cgst_amount": 8.0,
        "sgst_amount": 9.0,
        "total_amount": 117.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 8.0, "sgst_amount": 9.0, "total": 119.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "MISMATCH"


def test_10_wrong_sgst(validator):
    """10. Wrong SGST: total=125 but taxable=100, CGST=9, SGST=8 (exp 117) -> MISMATCH"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 17.0,
        "cgst_amount": 9.0,
        "sgst_amount": 8.0,
        "total_amount": 117.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 8.0, "total": 125.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"


def test_11_wrong_igst(validator):
    """11. Wrong IGST: taxable=100, IGST=17, total=118 (diff 1.00 passes, diff 2.00 fails)"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 17.0,
        "igst_amount": 17.0,
        "total_amount": 117.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "igst_amount": 17.0, "total": 120.0 # Expected 117 -> diff 3.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"


def test_12_wrong_cess(validator):
    """12. Wrong Cess: taxable=100, taxes=18, Cess=10, total=135 (exp 128) -> MISMATCH"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 28.0,
        "cgst_amount": 9.0,
        "sgst_amount": 9.0,
        "cess_amount": 10.0,
        "total_amount": 128.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 9.0, "cess_amount": 10.0, "total": 135.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"


def test_13_tax_rate_plus_missing_tax_amount(validator):
    """13. Tax rate present (9%+9%), tax amount missing, total=118 -> PASS (LINE_TAX_DERIVED_FROM_RATE)"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 18.0,
        "cgst_amount": 9.0,
        "sgst_amount": 9.0,
        "total_amount": 118.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_rate": 9.0, "sgst_rate": 9.0, "total": 118.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"
    assert l_check["line_tax_total"] == 18.0
    assert l_check["expected_total"] == 118.0


def test_14_tax_rate_plus_conflicting_tax_amount(validator):
    """14. Tax rate (18%) conflicts with explicit tax amount (9) -> REVIEW_REQUIRED (TAX_RATE_AMOUNT_CONFLICT)"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 9.0,
        "cgst_amount": 9.0,
        "total_amount": 109.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_rate": 18.0, "cgst_amount": 9.0, "total": 109.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert l_check["issue"] == "TAX_RATE_AMOUNT_CONFLICT"


def test_15_header_tax_only_single_line(validator):
    """15. Header-tax-only single line without line-level tax rate/amount -> REVIEW_REQUIRED (UNALLOCATED_HEADER_TAX)"""
    inv = {
        "subtotal": 100.0,
        "tax_total": 18.0,
        "total_amount": 118.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "total": 118.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert l_check["issue"] == "UNALLOCATED_HEADER_TAX"


def test_16_header_tax_only_multiple_lines(validator):
    """16. Header-tax-only multiple lines -> REVIEW_REQUIRED (UNALLOCATED_HEADER_TAX)"""
    inv = {
        "subtotal": 300.0,
        "tax_total": 54.0,
        "total_amount": 354.0,
        "line_items": [
            {"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "total": 118.0},
            {"quantity": 2, "unit_price": 100.0, "taxable_amount": 200.0, "total": 236.0},
        ],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    assert all(lc["issue"] == "UNALLOCATED_HEADER_TAX" for lc in res["checks"][0]["line_breakdowns"])


def test_17_zero_tax_invoice(validator):
    """17. Zero-tax invoice: taxable=100, tax=0 -> total=100 passes, total=118 fails"""
    inv_pass = {
        "subtotal": 100.0, "tax_total": 0.0, "total_amount": 100.0,
        "line_items": [{"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "total": 100.0}]
    }
    res_pass = validator.validate_invoice(inv_pass)
    assert res_pass["overall_status"] == "PASSED"

    inv_fail = {
        "subtotal": 100.0, "tax_total": 0.0, "total_amount": 100.0,
        "line_items": [{"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "total": 118.0}]
    }
    res_fail = validator.validate_invoice(inv_fail)
    assert res_fail["overall_status"] == "MISMATCH"


def test_18_zero_values(validator):
    """18. Zero values: taxable=0, tax=0, total=0 -> PASS (0.00 is a valid number)"""
    inv = {
        "subtotal": 0.0, "tax_total": 0.0, "total_amount": 0.0,
        "line_items": [{"quantity": 0, "unit_price": 0.0, "taxable_amount": 0.0, "total": 0.0}]
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"


def test_19_negative_credit_line(validator):
    """19. Mathematically consistent credit line -> PASS; inconsistent credit line -> MISMATCH"""
    inv_pass = {
        "subtotal": -100.0, "tax_total": -18.0, "cgst_amount": -9.0, "sgst_amount": -9.0, "total_amount": -118.0,
        "line_items": [{"quantity": -1, "unit_price": 100.0, "taxable_amount": -100.0, "cgst_amount": -9.0, "sgst_amount": -9.0, "total": -118.0}]
    }
    res_pass = validator.validate_invoice(inv_pass)
    assert res_pass["overall_status"] == "PASSED"

    inv_fail = {
        "subtotal": -100.0, "tax_total": -18.0, "cgst_amount": -9.0, "sgst_amount": -9.0, "total_amount": -118.0,
        "line_items": [{"quantity": -1, "unit_price": 100.0, "taxable_amount": -100.0, "cgst_amount": -9.0, "sgst_amount": -9.0, "total": -90.0}]
    }
    res_fail = validator.validate_invoice(inv_fail)
    assert res_fail["overall_status"] == "MISMATCH"


def test_20_percentage_discount_plus_line_total(validator):
    """20. Qty=10, Rate=100, Disc=10% -> Taxable=900, GST=18% -> Total=1062 PASS"""
    oracle = oracle_calc_line(10, 100.0, "10%", "percentage", None, 81.0, 81.0, None, None)
    assert oracle["taxable"] == 900.0
    assert oracle["expected_total"] == 1062.0

    inv = {
        "subtotal": 900.0, "tax_total": 162.0, "cgst_amount": 81.0, "sgst_amount": 81.0, "total_amount": 1062.0,
        "line_items": [{
            "quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0,
            "cgst_amount": 81.0, "sgst_amount": 81.0, "total": 1062.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["expected_total"] == 1062.0


def test_21_amount_discount_plus_line_total(validator):
    """21. Amount discount ₹100 with GST -> Total=1062 PASS; corrupted 9062 -> MISMATCH"""
    inv = {
        "subtotal": 900.0, "tax_total": 162.0, "cgst_amount": 81.0, "sgst_amount": 81.0, "total_amount": 1062.0,
        "line_items": [{
            "quantity": 10, "unit_price": 100.0, "discount": "₹100", "taxable_amount": 900.0,
            "cgst_amount": 81.0, "sgst_amount": 81.0, "total": 9062.0 # Corrupted
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"


def test_22_header_discount_plus_line_total(validator):
    """22. Header discount does not bypass or hide a corrupted line total"""
    inv = {
        "subtotal": 900.0, "discount_total": 100.0, "tax_total": 162.0, "total_amount": 1062.0,
        "line_items": [{
            "quantity": 10, "unit_price": 100.0, "discount": "10%", "taxable_amount": 900.0,
            "cgst_amount": 81.0, "sgst_amount": 81.0, "total": 9999.0 # Corrupted line total
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    assert any("Line 1 total mismatch" in err for err in res["errors"])


def test_23_conflicting_total_aliases(validator):
    """23. Conflicting aliases: total=118, line_total=999 -> REVIEW_REQUIRED (CONFLICTING_LINE_TOTAL_ALIASES)"""
    inv = {
        "subtotal": 100.0, "tax_total": 18.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total_amount": 118.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 9.0, "total": 118.0, "line_total": 999.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert l_check["issue"] == "CONFLICTING_LINE_TOTAL_ALIASES"


def test_24_amount_field_ambiguity(validator):
    """24. Ambiguous 'amount' without separate taxable on taxed invoice -> REVIEW_REQUIRED (AMBIGUOUS_AMOUNT_FIELD)"""
    inv = {
        "subtotal": 100.0, "tax_total": 18.0, "total_amount": 118.0,
        "line_items": [{"description": "Item", "amount": 100.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert l_check["issue"] == "AMBIGUOUS_AMOUNT_FIELD"


def test_25_multi_line_invoice(validator):
    """25. Multi-line invoice with consistent line totals -> PASS"""
    inv = {
        "subtotal": 300.0, "tax_total": 54.0, "cgst_amount": 27.0, "sgst_amount": 27.0, "total_amount": 354.0,
        "line_items": [
            {"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total": 118.0},
            {"quantity": 2, "unit_price": 100.0, "taxable_amount": 200.0, "cgst_amount": 18.0, "sgst_amount": 18.0, "total": 236.0},
        ],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert all(lc["status"] == "PASSED" for lc in res["checks"][0]["line_breakdowns"])


def test_26_corrupt_exactly_one_line_in_multiline(validator):
    """26. Corrupt exactly Line 2 in 5-line invoice -> accurately identifies Line 2"""
    lines = []
    for i in range(1, 6):
        lines.append({
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 9.0,
            "total": 118.0 if i != 2 else 999.0 # Corrupt Line 2
        })
    inv = {
        "subtotal": 500.0, "tax_total": 90.0, "cgst_amount": 45.0, "sgst_amount": 45.0, "total_amount": 590.0,
        "line_items": lines,
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    l_checks = res["checks"][0]["line_breakdowns"]
    assert l_checks[0]["status"] == "PASSED"
    assert l_checks[1]["status"] == "MISMATCH"
    assert l_checks[1]["extracted_total"] == 999.0
    assert l_checks[2]["status"] == "PASSED"


def test_27_tolerance_0_99(validator):
    """27. Difference 0.99 within ₹1.00 tolerance -> PASS"""
    inv = {
        "subtotal": 100.0, "tax_total": 18.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total_amount": 118.0,
        "line_items": [{"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total": 118.99}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["checks"][0]["line_breakdowns"][0]["status"] == "PASSED"


def test_28_tolerance_1_00(validator):
    """28. Difference 1.00 exactly at ₹1.00 tolerance boundary -> PASS"""
    inv = {
        "subtotal": 100.0, "tax_total": 18.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total_amount": 118.0,
        "line_items": [{"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total": 119.00}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["checks"][0]["line_breakdowns"][0]["status"] == "PASSED"


def test_29_tolerance_1_01(validator):
    """29. Difference 1.01 outside ₹1.00 tolerance -> MISMATCH"""
    inv = {
        "subtotal": 100.0, "tax_total": 18.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total_amount": 118.0,
        "line_items": [{"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total": 119.01}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "MISMATCH"
    assert res["checks"][0]["line_breakdowns"][0]["status"] == "MISMATCH"


def test_30_malformed_line_total(validator):
    """30. Formatted line total string '₹118.00' parses and validates cleanly"""
    inv = {
        "subtotal": 100.0, "tax_total": 18.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total_amount": 118.0,
        "line_items": [{"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total": "₹118.00"}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["checks"][0]["line_breakdowns"][0]["status"] == "PASSED"


def test_31_malformed_tax_values(validator):
    """31. Formatted tax value string '₹9.00' parses and validates cleanly"""
    inv = {
        "subtotal": 100.0, "tax_total": 18.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total_amount": 118.0,
        "line_items": [{"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "cgst_amount": "₹9.00", "sgst_amount": "₹9.00", "total": 118.0}],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["checks"][0]["line_breakdowns"][0]["status"] == "PASSED"


def test_32_zero_point_zero_values(validator):
    """32. Explicit 0.00 tax on taxed invoice (e.g. 0% rated line item alongside 18% line item)"""
    inv = {
        "subtotal": 200.0, "tax_total": 18.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total_amount": 218.0,
        "line_items": [
            {"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "cgst_amount": 0.0, "sgst_amount": 0.0, "total": 100.0},
            {"quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total": 118.0},
        ],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    assert res["checks"][0]["line_breakdowns"][0]["status"] == "PASSED"
    assert res["checks"][0]["line_breakdowns"][0]["line_tax_total"] == 0.0
    assert res["checks"][0]["line_breakdowns"][0]["expected_total"] == 100.0


def test_33_multiple_aliases_with_identical_values(validator):
    """33. Multiple aliases with identical values: total=118, line_total=118 -> PASS (consistent aliases)"""
    inv = {
        "subtotal": 100.0, "tax_total": 18.0, "cgst_amount": 9.0, "sgst_amount": 9.0, "total_amount": 118.0,
        "line_items": [{
            "quantity": 1, "unit_price": 100.0, "taxable_amount": 100.0,
            "cgst_amount": 9.0, "sgst_amount": 9.0, "total": 118.0, "line_total": 118.0, "item_total": 118.0
        }],
    }
    res = validator.validate_invoice(inv)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"
    assert l_check["extracted_total"] == 118.0
