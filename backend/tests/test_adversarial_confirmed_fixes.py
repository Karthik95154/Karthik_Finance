"""
Focused Regression Test Suite for the 3 Confirmed Adversarial Audit Fixes:
1. Non-finite numeric values (inf, -inf, nan, strings)
2. Raw tolerance comparison in GSTEngine intra-state pairing (diff > 1.00 raw)
3. Malformed comma numeric input (valid Indian/international vs malformed commas)
"""

import math
import pytest
from app.services.financial_validator import parse_clean_numeric as fv_parse
from app.services.gst_engine import GSTEngine, parse_clean_numeric as gst_parse

gst_engine = GSTEngine()


# ==============================================================================
# 1. NON-FINITE NUMERIC VALUES
# ==============================================================================
@pytest.mark.parametrize("parser_fn", [fv_parse, gst_parse])
@pytest.mark.parametrize("val", [
    float("inf"),
    float("-inf"),
    float("nan"),
    "inf",
    "-inf",
    "+inf",
    "Infinity",
    "-Infinity",
    "NaN",
    True,
    False,
])
def test_non_finite_and_boolean_rejected(parser_fn, val):
    assert parser_fn(val) is None, f"Parser {parser_fn.__name__} must reject {repr(val)}"


@pytest.mark.parametrize("parser_fn", [fv_parse, gst_parse])
@pytest.mark.parametrize("val,expected", [
    (100, 100.0),
    (100.0, 100.0),
    (0, 0.0),
    (-50.5, -50.5),
    ("100", 100.0),
    ("-100", -100.0),
    ("(100)", -100.0),
    ("0.0", 0.0),
    ("100.55", 100.55),
])
def test_valid_finite_numbers_preserved(parser_fn, val, expected):
    res = parser_fn(val)
    assert res == pytest.approx(expected, abs=1e-4)


# ==============================================================================
# 2. MALFORMED COMMA NUMERIC INPUT
# ==============================================================================
@pytest.mark.parametrize("parser_fn", [fv_parse, gst_parse])
@pytest.mark.parametrize("valid_str,expected", [
    ("1,000", 1000.0),
    ("10,000", 10000.0),
    ("1,00,000", 100000.0),
    ("12,34,567.89", 1234567.89),
    ("1,20,000", 120000.0),
    ("Rs. 1,00,000/-", 100000.0),
    ("₹ 1,500.00", 1500.0),
    ("(1,000.00)", -1000.0),
    ("1,000,000", 1000000.0),
])
def test_valid_comma_grouping_accepted(parser_fn, valid_str, expected):
    assert parser_fn(valid_str) == pytest.approx(expected, abs=1e-4)


@pytest.mark.parametrize("parser_fn", [fv_parse, gst_parse])
@pytest.mark.parametrize("malformed_str", [
    "1,,000",
    "1,00,,000",
    ",1000",
    "1000,",
    "1,000,",
    "1,,,000",
    "1,00,00,00",
    "12,,34",
    "1,,2,,3",
    ",1,000",
])
def test_malformed_comma_grouping_rejected(parser_fn, malformed_str):
    assert parser_fn(malformed_str) is None, f"Parser {parser_fn.__name__} must reject {repr(malformed_str)}"


# ==============================================================================
# 3. PREMATURE ROUNDING OF GST TOLERANCE (RAW ₹1.00 TEST)
# ==============================================================================
@pytest.mark.parametrize("c,s,expected_status", [
    (100.0, 100.0, "PASSED"),
    (100.0, 101.00, "PASSED"),
    (100.0, 99.00, "PASSED"),
    (100.0, 100.50, "PASSED"),
    (100.0, 99.50, "PASSED"),
    (100.0, 100.99, "PASSED"),
    (100.0, 99.01, "PASSED"),
    # Exact raw boundaries beyond 1.00 MUST be GST_MISMATCH
    (100.0, 101.0000001, "GST_MISMATCH"),
    (100.0, 101.0001, "GST_MISMATCH"),
    (100.0, 101.001, "GST_MISMATCH"),
    (100.0, 101.01, "GST_MISMATCH"),
    (100.0, 98.9999999, "GST_MISMATCH"),
    (100.0, 98.9999, "GST_MISMATCH"),
    (100.0, 98.999, "GST_MISMATCH"),
    (100.0, 98.99, "GST_MISMATCH"),
    (100.0, 102.0, "GST_MISMATCH"),
    (100.0, 98.0, "GST_MISMATCH"),
])
def test_cgst_sgst_raw_tolerance_boundary(c, s, expected_status):
    payload = {
        "subtotal": 1000.0,
        "cgst": c,
        "sgst": s,
        "tax_total": c + s,
        "grand_total": 1000.0 + c + s,
        "vendor_address": "Bangalore, Karnataka",
        "customer_address": "Bangalore, Karnataka",
    }
    res = gst_engine.evaluate_gst(payload)
    assert res.get("validation_status") == expected_status, (
        f"For CGST={c}, SGST={s} (raw diff={abs(c-s)}), expected {expected_status} but got {res.get('validation_status')}"
    )
