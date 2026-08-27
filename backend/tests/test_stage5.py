import pytest
from app.services.financial_validator import FinancialValidator, financial_validator


def test_1_exact_valid_invoice():
    """1. Exact valid invoice with matching lines, subtotal, taxes, and total -> PASSED"""
    invoice_data = {
        "subtotal": 5000.0,
        "cgst_amount": 450.0,
        "sgst_amount": 450.0,
        "igst_amount": 0.0,
        "tax_total": 900.0,
        "discount_total": 0.0,
        "shipping_charges": 0.0,
        "other_charges": 0.0,
        "round_off": 0.0,
        "total_amount": 5900.0,
        "line_items": [
            {
                "description": "Item A",
                "quantity": 2,
                "unit_price": 2500.0,
                "taxable_amount": 5000.0,
            }
        ],
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["subtotal"] == 5000.0
    assert res["calculated"]["gst_total"] == 900.0
    assert res["calculated"]["grand_total"] == 5900.0
    assert len(res["errors"]) == 0


def test_2_line_total_mismatch():
    """2. Line total arithmetic mismatch: 3 * 1000 = 3000, but extracted line total is 3500 -> MISMATCH"""
    invoice_data = {
        "subtotal": 3500.0,
        "total_amount": 3500.0,
        "line_items": [
            {
                "description": "Item A",
                "quantity": 3,
                "unit_price": 1000.0,
                "taxable_amount": 3500.0,  # Expected 3000.0
            }
        ],
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "MISMATCH"
    assert any("Line 1 math mismatch" in err for err in res["errors"])


def test_3_line_sum_vs_subtotal_mismatch():
    """3. Sum of line items does not equal extracted subtotal -> MISMATCH"""
    invoice_data = {
        "subtotal": 5000.0,
        "total_amount": 5000.0,
        "line_items": [
            {"description": "Item 1", "quantity": 1, "unit_price": 2000.0, "taxable_amount": 2000.0},
            {"description": "Item 2", "quantity": 1, "unit_price": 2000.0, "taxable_amount": 2000.0},
        ],  # Sum = 4000.0 != 5000.0
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "MISMATCH"
    assert any("Subtotal mismatch" in err for err in res["errors"])


def test_4_gst_component_mismatch():
    """4. GST components sum does not match extracted tax total -> MISMATCH"""
    invoice_data = {
        "subtotal": 1000.0,
        "cgst_amount": 100.0,
        "sgst_amount": 100.0,
        "tax_total": 250.0,  # Components sum = 200.0 != 250.0
        "total_amount": 1250.0,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "MISMATCH"
    assert any("GST components sum" in err for err in res["errors"])


def test_5_gst_total_mismatch():
    """5. Extracted Tax Total differs from calculated line taxes"""
    invoice_data = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 200.0,  # 90 + 90 = 180 != 200
        "total_amount": 1200.0,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "MISMATCH"
    gst_check = next(c for c in res["checks"] if c["name"] == "gst_components_vs_gst_total")
    assert gst_check["status"] == "MISMATCH"
    assert gst_check["difference"] == 20.0


def test_6_discount_included_correctly():
    """6. Invoice-level discount reduces total correctly: 1000 - 100 + 180 = 1080"""
    invoice_data = {
        "subtotal": 1000.0,
        "discount_total": 100.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 180.0,
        "total_amount": 1080.0,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["grand_total"] == 1080.0


def test_7_shipping_included_correctly():
    """7. Shipping charges added to total: 1000 + 180 + 50 = 1230"""
    invoice_data = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 180.0,
        "shipping_charges": 50.0,
        "total_amount": 1230.0,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["grand_total"] == 1230.0


def test_8_other_charges_included_correctly():
    """8. Other charges added to total: 1000 + 180 + 25 = 1205"""
    invoice_data = {
        "subtotal": 1000.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "tax_total": 180.0,
        "other_charges": 25.0,
        "total_amount": 1205.0,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["grand_total"] == 1205.0


def test_9_positive_round_off():
    """9. Positive round off added: 99.75 + 0.25 = 100.00"""
    invoice_data = {
        "subtotal": 84.53,
        "tax_total": 15.22,
        "cgst_amount": 7.61,
        "sgst_amount": 7.61,
        "round_off": 0.25,
        "total_amount": 100.00,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["grand_total"] == 100.00


def test_10_negative_round_off():
    """10. Negative round off subtracted: 100.20 - 0.20 = 100.00"""
    invoice_data = {
        "subtotal": 84.91,
        "tax_total": 15.29,
        "cgst_amount": 7.645,
        "sgst_amount": 7.645,
        "round_off": -0.20,
        "total_amount": 100.00,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["grand_total"] == 100.00


def test_11_grand_total_mismatch():
    """11. Grand total calculation mismatch: expected 1180, extracted 1500 -> MISMATCH"""
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "total_amount": 1500.0,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "MISMATCH"
    assert any("Grand Total mismatch" in err for err in res["errors"])


def test_12_within_tolerance_passed():
    """12. Difference within tolerance (<= 1.00) -> PASSED"""
    validator = FinancialValidator(tolerance=1.0)
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "total_amount": 1180.50,  # diff = 0.50 <= 1.0
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"


def test_13_outside_tolerance_mismatch():
    """13. Difference outside tolerance (> 1.00) -> MISMATCH"""
    validator = FinancialValidator(tolerance=1.0)
    invoice_data = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "total_amount": 1182.50,  # diff = 2.50 > 1.0
    }
    res = validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "MISMATCH"


def test_14_missing_required_fields_review_required():
    """14. Missing total amount or subtotal -> REVIEW_REQUIRED"""
    invoice_data = {
        "subtotal": None,
        "total_amount": None,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "REVIEW_REQUIRED"


def test_15_multiple_gst_rates():
    """15. Multi-line items with different rates aggregate to correct subtotal and grand total"""
    invoice_data = {
        "subtotal": 3000.0,
        "cgst_amount": 150.0,
        "sgst_amount": 150.0,
        "tax_total": 300.0,
        "total_amount": 3300.0,
        "line_items": [
            {"description": "5% Item", "quantity": 10, "unit_price": 100.0, "taxable_amount": 1000.0},
            {"description": "18% Item", "quantity": 20, "unit_price": 100.0, "taxable_amount": 2000.0},
        ],
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    assert res["calculated"]["subtotal"] == 3000.0
    assert res["calculated"]["grand_total"] == 3300.0


def test_16_extracted_values_preserved():
    """16. Extracted values preserved exactly in source dictionary"""
    invoice_data = {
        "subtotal": 12345.67,
        "discount_total": 100.0,
        "shipping_charges": 50.0,
        "other_charges": 20.0,
        "round_off": -0.17,
        "total_amount": 14000.0,
        "cgst_amount": 800.0,
        "sgst_amount": 800.0,
        "tax_total": 1600.0,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["source"]["subtotal"] == 12345.67
    assert res["source"]["discount_total"] == 100.0
    assert res["source"]["shipping_charges"] == 50.0
    assert res["source"]["other_charges"] == 20.0
    assert res["source"]["round_off"] == -0.17
    assert res["source"]["total_amount"] == 14000.0


def test_17_rs_888_extracted_tax_total_vs_882_calculated_gst():
    """17. Extracted Tax Total ₹888 vs Calculated GST ₹882 -> discrepancy detected and reported"""
    invoice_data = {
        "subtotal": 4900.0,
        "cgst_amount": 441.0,
        "sgst_amount": 441.0,
        "igst_amount": 0.0,
        "tax_total": 888.0,  # 441 + 441 = 882 != 888
        "total_amount": 5788.0,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "MISMATCH"
    gst_check = next(c for c in res["checks"] if c["name"] == "gst_components_vs_gst_total")
    assert gst_check["status"] == "MISMATCH"
    assert gst_check["source_value"] == 888.0
    assert gst_check["calculated_value"] == 882.0
    assert gst_check["difference"] == 6.0


def test_18_tds_is_not_included_in_gst_calculation():
    """18. TDS remains separate and is not added to GST components or total"""
    invoice_data = {
        "subtotal": 10000.0,
        "cgst_amount": 900.0,
        "sgst_amount": 900.0,
        "tax_total": 1800.0,
        "total_amount": 11800.0,
        "additional_fields": {
            "tds_amount": 200.0,
            "tds_rate": 2.0,
        },
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["overall_status"] == "PASSED"
    # GST total must be exactly 1800.0, not 2000.0
    assert res["calculated"]["gst_total"] == 1800.0
    assert res["calculated"]["grand_total"] == 11800.0


def test_19_no_fabricated_values():
    """19. Missing values are returned as None / 0 and not fabricated with random numbers"""
    invoice_data = {
        "subtotal": None,
        "cgst_amount": None,
        "sgst_amount": None,
        "total_amount": None,
    }
    res = financial_validator.validate_invoice(invoice_data)
    assert res["source"]["subtotal"] is None
    assert res["source"]["cgst_amount"] is None
    assert res["source"]["total_amount"] is None
    assert res["overall_status"] == "REVIEW_REQUIRED"


def test_20_customer_edit_flow_revalidates_financial_values():
    """20. Customer edit flow re-evaluates financial values upon data update"""
    # Initial invalid state
    invoice_data_before = {
        "subtotal": 1000.0,
        "tax_total": 180.0,
        "cgst_amount": 90.0,
        "sgst_amount": 90.0,
        "total_amount": 1500.0,  # Wrong total
    }
    res_before = financial_validator.validate_invoice(invoice_data_before)
    assert res_before["overall_status"] == "MISMATCH"

    # User corrects total_amount to 1180.0
    invoice_data_after = {
        **invoice_data_before,
        "total_amount": 1180.0,
    }
    res_after = financial_validator.validate_invoice(invoice_data_after)
    assert res_after["overall_status"] == "PASSED"
    assert res_after["calculated"]["grand_total"] == 1180.0
