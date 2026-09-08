"""
Regression test for GST line-item vs header reconciliation with exact user values.
"""
import pytest
from app.services.financial_validator import FinancialValidator

def test_gst_reconciliation_exact_user_scenario():
    validator = FinancialValidator(tolerance=0.05)

    # 6 line items totaling 863.00 CGST and 863.00 SGST
    line_items = [
        {"description": "Item 1", "quantity": 1, "unit_price": 11899.20, "taxable_amount": 11899.20, "cgst_rate": 2.5, "cgst_amount": 297.48, "sgst_rate": 2.5, "sgst_amount": 297.48, "total": 12494.16},
        {"description": "Item 2", "quantity": 1, "unit_price": 1069.00, "taxable_amount": 1069.00, "cgst_rate": 6.0, "cgst_amount": 64.14, "sgst_rate": 6.0, "sgst_amount": 64.14, "total": 1197.28},
        {"description": "Item 3", "quantity": 1, "unit_price": 4144.17, "taxable_amount": 4144.17, "cgst_rate": 6.0, "cgst_amount": 248.65, "sgst_rate": 6.0, "sgst_amount": 248.65, "total": 4641.47},
        {"description": "Item 4", "quantity": 1, "unit_price": 2250.17, "taxable_amount": 2250.17, "cgst_rate": 6.0, "cgst_amount": 135.01, "sgst_rate": 6.0, "sgst_amount": 135.01, "total": 2520.19},
        {"description": "Item 5", "quantity": 1, "unit_price": 988.00, "taxable_amount": 988.00, "cgst_rate": 6.0, "cgst_amount": 59.28, "sgst_rate": 6.0, "sgst_amount": 59.28, "total": 1106.56},
        {"description": "Item 6", "quantity": 1, "unit_price": 974.00, "taxable_amount": 974.00, "cgst_rate": 6.0, "cgst_amount": 58.44, "sgst_rate": 6.0, "sgst_amount": 58.44, "total": 1090.88},
    ]

    invoice_data = {
        "invoice_number": "INV-2026-001",
        "subtotal": 21324.54,
        "cgst_amount": 863.00,
        "sgst_amount": 863.00,
        "tax_total": 1726.00,
        "total_amount": 23050.54,
        "line_items": line_items,
    }

    result = validator.validate_invoice(invoice_data)

    recon_check = next((c for c in result["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation"), None)
    assert recon_check is not None
    assert recon_check["status"] == "PASSED"
    assert result["overall_status"] == "PASSED"


def test_discrepancy_banner_logic_test1_zero_tax():
    """Test 1: Header Tax = 0, Line Tax Sum = 0, Diff = 0 -> Expected: No discrepancy (PASSED)."""
    validator = FinancialValidator(tolerance=0.05)
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 0.0,
        "total_amount": 1000.0,
        "line_items": [{"description": "Item A", "taxable_amount": 1000.0, "total": 1000.0}],
    }
    result = validator.validate_invoice(invoice_data)
    assert result["overall_status"] == "PASSED"
    mismatches = [c for c in result.get("checks", []) if c.get("status") == "MISMATCH" and abs(c.get("difference", 0.0)) >= 0.01]
    assert len(mismatches) == 0


def test_discrepancy_banner_logic_test2_equal_cgst_sgst():
    """Test 2: Header CGST = 863, Line CGST = 863, Diff = 0 -> Expected: No discrepancy (PASSED)."""
    validator = FinancialValidator(tolerance=0.05)
    invoice_data = {
        "cgst_amount": 863.0,
        "sgst_amount": 863.0,
        "tax_total": 1726.0,
        "subtotal": 10000.0,
        "total_amount": 11726.0,
        "line_items": [
            {"cgst_amount": 863.0, "sgst_amount": 863.0, "taxable_amount": 10000.0, "total": 11726.0}
        ],
    }
    result = validator.validate_invoice(invoice_data)
    recon = next((c for c in result["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation"), None)
    assert recon is not None
    assert recon["status"] == "PASSED"
    mismatches = [c for c in result.get("checks", []) if c.get("status") == "MISMATCH" and abs(c.get("difference", 0.0)) >= 0.01]
    assert len(mismatches) == 0


def test_discrepancy_banner_logic_test3_genuine_mismatch():
    """Test 3: Header Tax = 1726, Line Tax Sum = 1092.26, Diff = 633.74 -> Expected: MISMATCH."""
    validator = FinancialValidator(tolerance=0.05)
    invoice_data = {
        "cgst_amount": 863.0,
        "sgst_amount": 863.0,
        "tax_total": 1726.0,
        "subtotal": 10000.0,
        "total_amount": 11726.0,
        "line_items": [
            {"description": "Item 1", "quantity": 1, "unit_price": 10000.0, "cgst_amount": 546.13, "sgst_amount": 546.13, "taxable_amount": 10000.0, "total": 11092.26}
        ],
    }
    result = validator.validate_invoice(invoice_data)
    recon = next((c for c in result["checks"] if c["name"] == "header_gst_vs_line_gst_reconciliation"), None)
    assert recon is not None
    assert recon["status"] == "MISMATCH"
    assert result["overall_status"] == "MISMATCH"
    mismatches = [c for c in result.get("checks", []) if c.get("status") == "MISMATCH" and abs(c.get("difference", 0.0)) >= 0.01]
    assert len(mismatches) > 0

