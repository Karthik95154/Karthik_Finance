import pytest
from app.services.gst_engine import gst_engine, parse_clean_numeric as gst_parse_numeric
from app.services.financial_validator import (
    FinancialValidator,
    financial_validator,
    parse_clean_numeric as fin_parse_numeric,
)

# ==============================================================================
# 1. GST ENGINE -> FINANCIAL VALIDATOR LINKAGE TESTS
# ==============================================================================

def test_linkage_gst_mismatch_fails_financial_validator():
    """GST Engine reports GST_MISMATCH on inter-state invoice with CGST/SGST -> FinancialValidator must not PASS."""
    p = {
        "vendor_gstin": "36AAECK1234Q1Z8",  # TS
        "customer_gstin": "27AABCM3344R1Z1",  # MH (Inter-state)
        "subtotal": 1000.0,
        "total_amount": 1180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 180.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "cgst_amount": 90.0,
                "sgst_amount": 90.0,
                "total": 1180.0,
            }
        ],
    }
    gst_res = gst_engine.evaluate_gst(p)
    assert gst_res["validation_status"] == "GST_MISMATCH"

    fin_res = financial_validator.validate_invoice(p, gst_result=gst_res)
    assert fin_res["overall_status"] == "MISMATCH"
    assert any("GST Engine error" in err for err in fin_res["errors"])
    link_check = next(c for c in fin_res["checks"] if c["name"] == "gst_engine_linkage")
    assert link_check["status"] == "MISMATCH"


def test_linkage_gst_review_required_propagates_to_financial_validator():
    """GST Engine reports REVIEW_REQUIRED when POS unresolved -> FinancialValidator must not PASS."""
    p = {
        "vendor_name": "Unregistered Vendor",
        "customer_name": "Client",
        "subtotal": 1000.0,
        "total_amount": 1180.0,
        "igst_amount": 180.0,
        "tax_total": 180.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "igst_amount": 180.0,
                "total": 1180.0,
            }
        ],
    }
    gst_res = gst_engine.evaluate_gst(p)
    assert gst_res["validation_status"] == "REVIEW_REQUIRED"

    fin_res = financial_validator.validate_invoice(p, gst_result=gst_res)
    assert fin_res["overall_status"] == "REVIEW_REQUIRED"
    link_check = next(c for c in fin_res["checks"] if c["name"] == "gst_engine_linkage")
    assert link_check["status"] == "REVIEW_REQUIRED"


def test_linkage_gst_passed_allows_financial_validator_pass():
    """GST Engine reports PASSED on valid intra-state invoice -> FinancialValidator passes cleanly."""
    p = {
        "vendor_gstin": "36AAECK1234Q1Z8",  # TS
        "customer_gstin": "36AABFR5678P1Z2",  # TS (Intra-state)
        "subtotal": 1000.0,
        "total_amount": 1180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 180.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "cgst_amount": 90.0,
                "sgst_amount": 90.0,
                "total": 1180.0,
            }
        ],
    }
    gst_res = gst_engine.evaluate_gst(p)
    assert gst_res["validation_status"] == "PASSED"

    fin_res = financial_validator.validate_invoice(p, gst_result=gst_res)
    assert fin_res["overall_status"] == "PASSED"


# ==============================================================================
# 2. INTRA-STATE CGST / SGST PAIRING TESTS
# ==============================================================================

def test_intra_state_cgst_without_sgst_fails():
    """Intra-state invoice with CGST present but SGST absent -> GST_MISMATCH."""
    p = {
        "vendor_gstin": "36AAECK1234Q1Z8",  # TS
        "customer_gstin": "36AABFR5678P1Z2",  # TS
        "subtotal": 1000.0,
        "total_amount": 1090.0,
        "cgst_amount": 90.0,
        "sgst_amount": None,
        "tax_total": 90.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "cgst_amount": 90.0,
                "total": 1090.0,
            }
        ],
    }
    gst_res = gst_engine.evaluate_gst(p)
    assert gst_res["validation_status"] == "GST_MISMATCH"
    assert any("Incomplete Intra-State GST breakdown" in err for err in gst_res["errors"])

    fin_res = financial_validator.validate_invoice(p, gst_result=gst_res)
    assert fin_res["overall_status"] == "MISMATCH"


def test_intra_state_sgst_without_cgst_fails():
    """Intra-state invoice with SGST present but CGST absent -> GST_MISMATCH."""
    p = {
        "vendor_gstin": "36AAECK1234Q1Z8",  # TS
        "customer_gstin": "36AABFR5678P1Z2",  # TS
        "subtotal": 1000.0,
        "total_amount": 1090.0,
        "cgst_amount": None,
        "sgst_amount": 90.0,
        "tax_total": 90.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "sgst_amount": 90.0,
                "total": 1090.0,
            }
        ],
    }
    gst_res = gst_engine.evaluate_gst(p)
    assert gst_res["validation_status"] == "GST_MISMATCH"
    assert any("Incomplete Intra-State GST breakdown" in err for err in gst_res["errors"])

    fin_res = financial_validator.validate_invoice(p, gst_result=gst_res)
    assert fin_res["overall_status"] == "MISMATCH"


def test_intra_state_cgst_sgst_mismatch_beyond_tolerance_fails():
    """Intra-state invoice with unequal CGST and SGST (diff > ₹1.00) -> GST_MISMATCH."""
    p = {
        "vendor_gstin": "36AAECK1234Q1Z8",
        "customer_gstin": "36AABFR5678P1Z2",
        "subtotal": 1000.0,
        "total_amount": 1180.0,
        "cgst_amount": 100.0,
        "sgst_amount": 80.0,  # diff = 20 > 1.00
        "tax_total": 180.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "cgst_amount": 100.0,
                "sgst_amount": 80.0,
                "total": 1180.0,
            }
        ],
    }
    gst_res = gst_engine.evaluate_gst(p)
    assert gst_res["validation_status"] == "GST_MISMATCH"
    assert any("CGST" in err and "SGST" in err and "mismatch" in err for err in gst_res["errors"])


def test_intra_state_cgst_sgst_within_tolerance_passes():
    """Intra-state invoice with CGST and SGST within ₹1.00 rounding tolerance -> PASSED."""
    p = {
        "vendor_gstin": "36AAECK1234Q1Z8",
        "customer_gstin": "36AABFR5678P1Z2",
        "subtotal": 1000.0,
        "total_amount": 1180.0,
        "cgst_amount": 90.25,
        "sgst_amount": 89.75,  # diff = 0.50 <= 1.00
        "tax_total": 180.0,
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "cgst_amount": 90.25,
                "sgst_amount": 89.75,
                "total": 1180.0,
            }
        ],
    }
    gst_res = gst_engine.evaluate_gst(p)
    assert gst_res["validation_status"] == "PASSED"


# ==============================================================================
# 3. NUMERIC PARSING HARDENING TESTS
# ==============================================================================

@pytest.mark.parametrize("parser", [fin_parse_numeric, gst_parse_numeric])
def test_numeric_parsing_hardening(parser):
    """Test numeric parser prevents silent corruption on booleans, scientific notation, and alphanumerics."""
    # Booleans must never be numeric
    assert parser(True) is None
    assert parser(False) is None

    # Alphanumerics must not be silently truncated to digits
    assert parser("12abc") is None
    assert parser("abc12") is None
    assert parser("1e3") is None
    assert parser("1e-5") is None

    # Malformed punctuation
    assert parser("12.34.56") is None
    assert parser("--50") is None

    # Valid inputs must continue working
    assert parser(100) == 100.0
    assert parser(100.55) == 100.55
    assert parser("120000") == 120000.0
    assert parser("1,20,000") == 120000.0
    assert parser("120000.00") == 120000.0
    assert parser("  150.0  ") == 150.0
    assert parser("0") == 0.0
    assert parser("0.00") == 0.0
    assert parser("-50.0") == -50.0
    assert parser("(50.0)") == -50.0

    # Currency prefixes and suffixes
    assert parser("Rs. 500.00") == 500.0
    assert parser("₹ 1,500.00/-") == 1500.0
    assert parser("10%") == 10.0


# ==============================================================================
# 4. ZERO RATE / ZERO TAXABLE EDGE CASES
# ==============================================================================

def test_explicit_zero_rate_with_nonzero_tax_requires_review():
    """Explicit rate = 0.0 but tax > 0 -> TAX_RATE_AMOUNT_CONFLICT -> REVIEW_REQUIRED."""
    p = {
        "subtotal": 1000.0,
        "total_amount": 1050.0,
        "igst_amount": 50.0,
        "tax_total": 50.0,
        "line_items": [
            {
                "description": "Item",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "igst_rate": 0.0,
                "igst_amount": 50.0,  # Conflict: 0% implies ₹0, but ₹50 charged
                "total": 1050.0,
            }
        ],
    }
    fin_res = financial_validator.validate_invoice(p)
    assert fin_res["overall_status"] == "REVIEW_REQUIRED"
    l_check = fin_res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert l_check["issue"] == "TAX_RATE_AMOUNT_CONFLICT"


def test_zero_taxable_with_nonzero_tax_requires_review():
    """Taxable = 0.0 but tax = 180.0 with 18% rate -> TAX_RATE_AMOUNT_CONFLICT -> REVIEW_REQUIRED."""
    p = {
        "subtotal": 0.0,
        "total_amount": 180.0,
        "igst_amount": 180.0,
        "tax_total": 180.0,
        "line_items": [
            {
                "description": "Item",
                "quantity": 1,
                "unit_price": 0.0,
                "taxable_amount": 0.0,
                "igst_rate": 18.0,
                "igst_amount": 180.0,  # 18% on ₹0 implies ₹0, but ₹180 charged
                "total": 180.0,
            }
        ],
    }
    fin_res = financial_validator.validate_invoice(p)
    assert fin_res["overall_status"] == "REVIEW_REQUIRED"
    l_check = fin_res["checks"][0]["line_breakdowns"][0]
    assert l_check["status"] == "REVIEW_REQUIRED"
    assert l_check["issue"] == "TAX_RATE_AMOUNT_CONFLICT"


def test_zero_rate_with_zero_tax_passes():
    """Exempt item with rate = 0% and tax = 0 -> PASSED."""
    p = {
        "subtotal": 1000.0,
        "total_amount": 1000.0,
        "igst_amount": 0.0,
        "tax_total": 0.0,
        "line_items": [
            {
                "description": "Item",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "igst_rate": 0.0,
                "igst_amount": 0.0,
                "total": 1000.0,
            }
        ],
    }
    fin_res = financial_validator.validate_invoice(p)
    assert fin_res["overall_status"] == "PASSED"


# ==============================================================================
# 5. CONFLICTING HEADER NUMERIC ALIASES
# ==============================================================================

def test_conflicting_total_amount_vs_grand_total_flags_review():
    """total_amount = 1180.0 vs grand_total = 1280.0 -> REVIEW_REQUIRED."""
    p = {
        "subtotal": 1000.0,
        "total_amount": 1180.0,
        "grand_total": 1280.0,  # Conflicting alias!
        "igst_amount": 180.0,
        "tax_total": 180.0,
        "line_items": [
            {
                "description": "Item",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "igst_amount": 180.0,
                "total": 1180.0,
            }
        ],
    }
    fin_res = financial_validator.validate_invoice(p)
    assert fin_res["overall_status"] == "REVIEW_REQUIRED"
    assert any("CONFLICTING_HEADER_ALIASES" in w for w in fin_res["warnings"])
    alias_check = next(c for c in fin_res["checks"] if c["name"] == "conflicting_header_aliases")
    assert alias_check["status"] == "REVIEW_REQUIRED"


def test_consistent_total_amount_and_grand_total_passes():
    """total_amount = 1180.0 and grand_total = 1180.0 -> PASSED cleanly."""
    p = {
        "subtotal": 1000.0,
        "total_amount": 1180.0,
        "grand_total": 1180.0,
        "igst_amount": 180.0,
        "tax_total": 180.0,
        "line_items": [
            {
                "description": "Item",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "igst_amount": 180.0,
                "total": 1180.0,
            }
        ],
    }
    fin_res = financial_validator.validate_invoice(p)
    assert fin_res["overall_status"] == "PASSED"
    assert not any("CONFLICTING_HEADER_ALIASES" in w for w in fin_res["warnings"])


def test_conflicting_subtotal_vs_taxable_amount_flags_review():
    """subtotal = 1000.0 vs taxable_amount = 1200.0 -> REVIEW_REQUIRED."""
    p = {
        "subtotal": 1000.0,
        "taxable_amount": 1200.0,  # Conflicting alias!
        "total_amount": 1180.0,
        "igst_amount": 180.0,
        "tax_total": 180.0,
        "line_items": [
            {
                "description": "Item",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "igst_amount": 180.0,
                "total": 1180.0,
            }
        ],
    }
    fin_res = financial_validator.validate_invoice(p)
    assert fin_res["overall_status"] == "REVIEW_REQUIRED"
    assert any("CONFLICTING_HEADER_ALIASES" in w for w in fin_res["warnings"])


def test_conflicting_tax_total_vs_total_tax_flags_review():
    """tax_total = 180.0 vs total_tax = 200.0 -> REVIEW_REQUIRED."""
    p = {
        "subtotal": 1000.0,
        "total_amount": 1180.0,
        "tax_total": 180.0,
        "total_tax": 200.0,  # Conflicting alias!
        "igst_amount": 180.0,
        "line_items": [
            {
                "description": "Item",
                "quantity": 1,
                "unit_price": 1000.0,
                "taxable_amount": 1000.0,
                "igst_amount": 180.0,
                "total": 1180.0,
            }
        ],
    }
    fin_res = financial_validator.validate_invoice(p)
    assert fin_res["overall_status"] == "REVIEW_REQUIRED"
    assert any("CONFLICTING_HEADER_ALIASES" in w for w in fin_res["warnings"])
