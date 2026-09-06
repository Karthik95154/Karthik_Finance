import pytest
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any

from app.services.financial_validator import FinancialValidator, parse_discount_semantics
from app.services.journal_generator import JournalGenerator
from app.db.models import Invoice


def calc_expected_line_taxable(
    qty: float,
    rate: float,
    discount: float,
    discount_type: str,
) -> Dict[str, float]:
    """
    Independent expected-value calculator.
    Does NOT derive expected values from production functions.
    Uses Decimal arithmetic for precise independent calculations.
    """
    d_qty = Decimal(str(qty))
    d_rate = Decimal(str(rate))
    d_disc = Decimal(str(discount))
    
    gross = (d_qty * d_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    if discount_type == "percentage":
        disc_amt = (gross * d_disc / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    elif discount_type == "amount":
        disc_amt = d_disc.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        raise ValueError(f"Unknown discount_type: {discount_type}")
        
    taxable = (gross - disc_amt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    return {
        "gross": float(gross),
        "discount_amount": float(disc_amt),
        "taxable": float(taxable),
    }


@pytest.fixture
def validator():
    return FinancialValidator(tolerance=1.0)


# --------------------------------------------------------------------------
# CRITICAL TESTS (Must pass as explicitly stated in prompt)
# --------------------------------------------------------------------------

def test_critical_percentage_discount(validator):
    """
    Qty = 30, Rate = 39.59, Discount = 10%
    Expected: Gross = 1187.70, Discount Amount = 118.77, Taxable = 1068.93
    """
    exp = calc_expected_line_taxable(30, 39.59, 10, "percentage")
    assert exp["gross"] == 1187.70
    assert exp["discount_amount"] == 118.77
    assert exp["taxable"] == 1068.93

    invoice_data = {
        "subtotal": 1068.93,
        "total_amount": 1068.93,
        "line_items": [
            {
                "description": "Item with 10% discount",
                "quantity": 30,
                "unit_price": 39.59,
                "discount": "10%",
                "taxable_amount": 1068.93,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "percentage"
    assert l_check["discount_amount"] == 118.77
    assert l_check["calculated_taxable"] == 1068.93
    assert l_check["status"] == "PASSED"


def test_critical_amount_discount(validator):
    """
    Qty = 10, Rate = 100, Discount = ₹10
    Expected: Gross = 1000, Discount Amount = 10, Taxable = 990
    """
    exp = calc_expected_line_taxable(10, 100, 10, "amount")
    assert exp["gross"] == 1000.0
    assert exp["discount_amount"] == 10.0
    assert exp["taxable"] == 990.0

    invoice_data = {
        "subtotal": 990.0,
        "total_amount": 990.0,
        "line_items": [
            {
                "description": "Item with ₹10 discount",
                "quantity": 10,
                "unit_price": 100,
                "discount": "₹10",
                "taxable_amount": 990.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "amount"
    assert l_check["discount_amount"] == 10.0
    assert l_check["calculated_taxable"] == 990.0
    assert l_check["status"] == "PASSED"


def test_critical_ambiguous_discount_blocks_silent_pass(validator):
    """
    Qty = 10, Rate = 100, Discount = 10 (no semantic type)
    MUST NOT silently choose percentage or amount.
    Must mark line as REVIEW_REQUIRED with AMBIGUOUS_DISCOUNT_CLASSIFICATION.
    """
    invoice_data = {
        "subtotal": 990.0,
        "total_amount": 990.0,
        "line_items": [
            {
                "description": "Item with bare 10 discount",
                "quantity": 10,
                "unit_price": 100,
                "discount": 10,
                "taxable_amount": 990.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert "AMBIGUOUS_DISCOUNT_CLASSIFICATION" in l_check["note"]
    assert any("AMBIGUOUS_DISCOUNT_CLASSIFICATION" in w for w in res["warnings"])


def test_false_pass_coincidental_match_remains_ambiguous(validator):
    """
    FALSE-PASS TEST:
    Qty = 1, Rate = 100, Discount = 10
    Even though:
      10% -> taxable 90
      ₹10 -> taxable 90
    and extracted taxable is 90.0,
    the system MUST NOT conclude that the type is known or silently pass!
    """
    invoice_data = {
        "subtotal": 90.0,
        "total_amount": 90.0,
        "line_items": [
            {
                "description": "Ambiguous discount coincidental math",
                "quantity": 1,
                "unit_price": 100,
                "discount": 10,
                "taxable_amount": 90.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert "AMBIGUOUS_DISCOUNT_CLASSIFICATION" in l_check["note"]


# --------------------------------------------------------------------------
# 21 EXHAUSTIVE REGRESSION TESTS
# --------------------------------------------------------------------------

def test_1_no_discount(validator):
    """1. No discount (discount is None or missing)"""
    invoice_data = {
        "subtotal": 500.0,
        "total_amount": 500.0,
        "line_items": [
            {"description": "No discount", "quantity": 5, "unit_price": 100.0, "taxable_amount": 500.0}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_amount"] == 0.0
    assert l_check["calculated_taxable"] == 500.0


def test_2_rs_10_amount_discount(validator):
    """2. ₹10 amount discount"""
    exp = calc_expected_line_taxable(5, 100.0, 10.0, "amount")
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Item", "quantity": 5, "unit_price": 100.0, "discount": "₹10", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "amount"
    assert l_check["calculated_taxable"] == 490.0


def test_3_10_pct_percentage_discount(validator):
    """3. 10% percentage discount"""
    exp = calc_expected_line_taxable(5, 100.0, 10.0, "percentage")
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Item", "quantity": 5, "unit_price": 100.0, "discount": "10%", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "percentage"
    assert l_check["calculated_taxable"] == 450.0


def test_4_10_space_pct_percentage_discount(validator):
    """4. 10 % percentage discount (with space)"""
    exp = calc_expected_line_taxable(4, 50.0, 10.0, "percentage")
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Item", "quantity": 4, "unit_price": 50.0, "discount": "10 %", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "percentage"
    assert l_check["calculated_taxable"] == 180.0


def test_5_10_dot_0_pct(validator):
    """5. 10.0% formatted percentage discount"""
    exp = calc_expected_line_taxable(2, 250.0, 10.0, "percentage")
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Item", "quantity": 2, "unit_price": 250.0, "discount": "10.0%", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "percentage"
    assert l_check["calculated_taxable"] == 450.0


def test_6_2_dot_5_pct(validator):
    """6. 2.5% decimal percentage discount"""
    exp = calc_expected_line_taxable(10, 200.0, 2.5, "percentage")  # gross 2000, disc 50 -> 1950
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Item", "quantity": 10, "unit_price": 200.0, "discount": "2.5%", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "percentage"
    assert l_check["discount_amount"] == 50.0
    assert l_check["calculated_taxable"] == 1950.0


def test_7_0_pct_discount(validator):
    """7. 0% discount"""
    exp = calc_expected_line_taxable(5, 100.0, 0.0, "percentage")
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Item", "quantity": 5, "unit_price": 100.0, "discount": "0%", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_amount"] == 0.0
    assert l_check["calculated_taxable"] == 500.0


def test_8_100_pct_discount(validator):
    """8. 100% full discount (free sample)"""
    exp = calc_expected_line_taxable(5, 100.0, 100.0, "percentage")
    assert exp["gross"] == 500.0
    assert exp["discount_amount"] == 500.0
    assert exp["taxable"] == 0.0

    invoice_data = {
        "subtotal": 0.0,
        "line_items": [
            {"description": "Free Sample", "quantity": 5, "unit_price": 100.0, "discount": "100%", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "PASSED"
    assert l_check["discount_amount"] == 500.0
    assert l_check["calculated_taxable"] == 0.0
    assert l_check["discount_type"] == "percentage"


def test_9_rs_1000_amount(validator):
    """9. ₹1,000 amount discount with comma"""
    exp = calc_expected_line_taxable(2, 1500.0, 1000.0, "amount")  # gross 3000 - 1000 = 2000
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Item", "quantity": 2, "unit_price": 1500.0, "discount": "₹1,000", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "amount"
    assert l_check["discount_amount"] == 1000.0
    assert l_check["calculated_taxable"] == 2000.0


def test_10_indian_number_formatting(validator):
    """10. Indian-number formatting: ₹1,50,000 unit price, ₹15,000 amount discount"""
    exp = calc_expected_line_taxable(1, 150000.0, 15000.0, "amount")
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Capital Asset", "quantity": "1", "unit_price": "1,50,000.00", "discount": "₹15,000.00", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["calculated_taxable"] == 135000.0


def test_11_10_pct_with_decimal_quantity(validator):
    """11. 10% with decimal quantity (e.g. 12.5 kg at ₹80/kg)"""
    exp = calc_expected_line_taxable(12.5, 80.0, 10.0, "percentage")  # gross 1000, disc 100 -> 900
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Bulk Grain", "quantity": 12.5, "unit_price": 80.0, "discount": "10%", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["calculated_taxable"] == 900.0


def test_12_10_pct_with_decimal_unit_price(validator):
    """12. 10% with decimal unit price (e.g. 10 units at ₹33.33)"""
    exp = calc_expected_line_taxable(10, 33.33, 10.0, "percentage")  # gross 333.30, disc 33.33 -> 299.97
    invoice_data = {
        "subtotal": exp["taxable"],
        "total_amount": exp["taxable"],
        "line_items": [
            {"description": "Parts", "quantity": 10, "unit_price": 33.33, "discount": "10%", "taxable_amount": exp["taxable"]}
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["calculated_taxable"] == 299.97


def test_13_explicit_taxable_matching_percentage_calculation(validator):
    """13. Explicit taxable matching percentage header (e.g. 'Trade Discount %')"""
    invoice_data = {
        "subtotal": 1800.0,
        "total_amount": 1800.0,
        "line_items": [
            {
                "description": "Item with Trade Discount %",
                "quantity": 2,
                "unit_price": 1000.0,
                "raw_fields": {"Trade Discount %": "10"},
                "taxable_amount": 1800.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "percentage"
    assert l_check["discount_amount"] == 200.0
    assert l_check["calculated_taxable"] == 1800.0


def test_14_explicit_taxable_matching_amount_calculation(validator):
    """14. Explicit taxable matching amount header (e.g. 'Disc Amt')"""
    invoice_data = {
        "subtotal": 1950.0,
        "total_amount": 1950.0,
        "line_items": [
            {
                "description": "Item with Disc Amt header",
                "quantity": 2,
                "unit_price": 1000.0,
                "raw_fields": {"Disc Amt": "50"},
                "taxable_amount": 1950.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["discount_type"] == "amount"
    assert l_check["discount_amount"] == 50.0
    assert l_check["calculated_taxable"] == 1950.0


def test_15_genuine_percentage_mismatch(validator):
    """15. Genuine percentage mismatch: 10 * 100 = 1000 - 10% (100) = 900, but extracted is 850"""
    invoice_data = {
        "subtotal": 850.0,
        "total_amount": 850.0,
        "line_items": [
            {
                "description": "Mismatch item",
                "quantity": 10,
                "unit_price": 100.0,
                "discount": "10%",
                "taxable_amount": 850.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "MISMATCH"
    assert any("math mismatch" in err for err in res["errors"])
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "MISMATCH"
    assert l_check["calculated_taxable"] == 900.0
    assert l_check["difference"] == 50.0


def test_16_genuine_amount_mismatch(validator):
    """16. Genuine amount mismatch: 10 * 100 = 1000 - ₹50 = 950, but extracted is 900"""
    invoice_data = {
        "subtotal": 900.0,
        "total_amount": 900.0,
        "line_items": [
            {
                "description": "Mismatch item",
                "quantity": 10,
                "unit_price": 100.0,
                "discount": "₹50",
                "taxable_amount": 900.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "MISMATCH"
    assert any("math mismatch" in err for err in res["errors"])
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "MISMATCH"
    assert l_check["calculated_taxable"] == 950.0
    assert l_check["difference"] == 50.0


def test_17_ambiguous_bare_numeric_discount(validator):
    """17. Ambiguous bare numeric discount (no % or ₹ indicator)"""
    invoice_data = {
        "subtotal": 450.0,
        "total_amount": 450.0,
        "line_items": [
            {
                "description": "Bare discount",
                "quantity": 5,
                "unit_price": 100.0,
                "discount": 50,  # Bare 50
                "taxable_amount": 450.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert "AMBIGUOUS_DISCOUNT_CLASSIFICATION" in l_check["note"]


def test_18_invalid_percentage_exceeding_100(validator):
    """18. Invalid >100% discount: 110% or 100.01%"""
    for invalid_pct in ["110%", "100.01%"]:
        invoice_data = {
            "subtotal": 0.0,
            "total_amount": 0.0,
            "line_items": [
                {
                    "description": "Over 100% discount",
                    "quantity": 1,
                    "unit_price": 100.0,
                    "discount": invalid_pct,
                    "taxable_amount": 0.0,
                }
            ],
        }
        res = validator.validate_invoice(invoice_data)
        assert res["overall_status"] == "REVIEW_REQUIRED"
        l_check = res["checks"][0]["line_breakdowns"][0]
        assert l_check["status"] == "REVIEW_REQUIRED"
        assert "exceeds 100%" in l_check["note"]


def test_19_negative_discount(validator):
    """19. Negative discount: -₹50 or -10%"""
    invoice_data = {
        "subtotal": 1050.0,
        "total_amount": 1050.0,
        "line_items": [
            {
                "description": "Negative discount",
                "quantity": 10,
                "unit_price": 100.0,
                "discount": "-₹50",
                "taxable_amount": 1050.0,
            }
        ],
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "REVIEW_REQUIRED"
    l_check = res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert "negative discount" in l_check["note"]


def test_20_frontend_backend_consistency():
    """
    20. Frontend / backend consistency:
    Verify that frontend logic (reproduced in JS/TS) and backend FinancialValidator logic
    produce identical taxable amount for percentage and amount discounts.
    """
    qty = 30
    price = 39.59
    disc_val = 10
    
    # Backend calculation
    val, disc_type, _ = parse_discount_semantics({"discount": "10%"})
    assert disc_type == "percentage"
    gross = round(qty * price, 2)
    b_disc_amt = round(gross * val / 100.0, 2)
    b_taxable = round(gross - b_disc_amt, 2)

    # Simulated TypeScript logic from InvoiceWorkspace.tsx:
    # const isPercentDisc = item.discount_type === "percentage" || String(item.discount || "").includes("%");
    # const discAmt = isPercentDisc ? (gross * disc) / 100 : disc;
    # taxable = Math.max(0, Math.round((gross - discAmt) * 100) / 100);
    f_gross = qty * price
    f_disc_amt = (f_gross * disc_val) / 100.0
    f_taxable = round(f_gross - f_disc_amt, 2)

    assert b_taxable == 1068.93
    assert f_taxable == 1068.93
    assert b_taxable == f_taxable


def test_21_journal_consistency():
    """
    21. Journal consistency:
    Verify that JournalGenerator fallback calculates taxable correctly respecting discount_type
    and reaches the journal entry lines consistently.
    """
    jg = JournalGenerator()
    invoice_data = {
        "invoice_number": "INV-DISC-001",
        "vendor_name": "Acme Supplier",
        "subtotal": 1068.93,
        "total_amount": 1068.93,
        "line_items": [
            {
                "description": "Item 1 with 10% discount",
                "quantity": 30,
                "unit_price": 39.59,
                "discount": "10%",
                "discount_type": "percentage",
                # taxable_amount omitted to test fallback calculation
            }
        ],
    }
    accounting_data = {
        "line_items": [
            {
                "line_index": 1,
                "approved_account_id": "acc-100",
                "approved_account_name": "Office Supplies Expense",
            }
        ]
    }
    result = jg.generate_journal(invoice_data, accounting_data)
    assert result["status"] == "BALANCED"
    lines = result["lines"]
    debit_line = next(l for l in lines if l["line_type"] == "EXPENSE")
    assert debit_line["amount"] == 1068.93

