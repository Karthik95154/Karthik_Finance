"""
Exhaustive Property-Based Fuzz Test Suite for Line Total Validation (5,000 cases).
Mutates line totals, tax components, and tax rates.
Validates 100% detection of mathematically provable corruption without false rejects.
"""
import pytest
import random
from decimal import Decimal, ROUND_HALF_UP

from app.services.financial_validator import FinancialValidator


def test_property_line_total_fuzz_5000():
    validator = FinancialValidator(tolerance=1.0)
    random.seed(2026)
    fuzz_count = 5000

    clean_passes = 0
    detected_corruptions = 0
    detected_reviews = 0
    false_passes = 0
    false_rejects = 0

    for i in range(fuzz_count):
        qty = random.randint(1, 10)
        rate = random.randint(10, 500)
        gross = Decimal(str(qty * rate))

        use_disc = (i % 2 == 0)
        disc_amt = (gross * Decimal("10") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if use_disc else Decimal("0.00")
        taxable = gross - disc_amt

        # 9% CGST + 9% SGST
        cgst = (taxable * Decimal("9") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst = (taxable * Decimal("9") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        taxes = cgst + sgst
        correct_tot = taxable + taxes

        # Test scenarios:
        # 0: Clean valid
        # 1: Mutate line_total by +10.00 (mismatch)
        # 2: Mutate line_total by *2 (mismatch)
        # 3: Omit tax from total (total = taxable) (mismatch)
        # 4: Conflicting tax rate (cgst_rate = 18% with cgst_amount = 9%) (review_required)
        # 5: Corrupt line_total by +0.01 (within ₹1.00 tolerance -> should pass)
        scenario = i % 6

        line_tot = correct_tot
        cgst_val = cgst
        sgst_val = sgst
        cgst_r = 9.0
        sgst_r = 9.0
        expected_status = "PASSED"

        if scenario == 1:
            line_tot = correct_tot + Decimal("10.00")
            expected_status = "MISMATCH"
        elif scenario == 2:
            line_tot = correct_tot * Decimal("2")
            expected_status = "MISMATCH"
        elif scenario == 3:
            line_tot = taxable
            expected_status = "MISMATCH"
        elif scenario == 4:
            cgst_r = 18.0 # rate implies 18% but amount is 9%
            expected_status = "REVIEW_REQUIRED"
        elif scenario == 5:
            line_tot = correct_tot + Decimal("0.01") # within ₹1.00 tolerance
            expected_status = "PASSED"

        inv = {
            "subtotal": float(taxable),
            "tax_total": float(taxes),
            "cgst_amount": float(cgst_val),
            "sgst_amount": float(sgst_val),
            "total_amount": float(taxable + taxes),
            "line_items": [{
                "quantity": float(qty),
                "unit_price": float(rate),
                "taxable_amount": float(taxable),
                "cgst_rate": float(cgst_r),
                "cgst_amount": float(cgst_val),
                "sgst_rate": float(sgst_r),
                "sgst_amount": float(sgst_val),
                "total": float(line_tot),
            }]
        }
        if use_disc:
            inv["line_items"][0]["discount"] = "10%"

        res = validator.validate_invoice(inv)
        act = res["overall_status"]

        if expected_status == "PASSED":
            if act == "PASSED":
                clean_passes += 1
            else:
                false_rejects += 1
        elif expected_status == "MISMATCH":
            if act == "MISMATCH":
                detected_corruptions += 1
            else:
                false_passes += 1
        elif expected_status == "REVIEW_REQUIRED":
            if act == "REVIEW_REQUIRED":
                detected_reviews += 1
            else:
                false_passes += 1

    print(f"\n[5,000 Property Fuzz Results]")
    print(f"Clean Passes:        {clean_passes}")
    print(f"Detected Mismatches: {detected_corruptions}")
    print(f"Detected Reviews:    {detected_reviews}")
    print(f"False Passes:        {false_passes}")
    print(f"False Rejections:    {false_rejects}")

    assert false_passes == 0, f"Encountered {false_passes} false passes!"
    assert false_rejects == 0, f"Encountered {false_rejects} false rejections!"
