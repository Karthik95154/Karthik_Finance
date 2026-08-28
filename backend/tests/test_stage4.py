import pytest
from app.services.gst_engine import gst_engine, validate_gstin, resolve_state_from_text
from app.services.itc_engine import itc_engine


def test_1_same_state_gstin_same_pos():
    """1. Same-state GSTIN + same POS -> INTRA_STATE -> CGST + SGST"""
    invoice_data = {
        "vendor_gstin": "36AABCU9603R1ZM",  # Telangana (36)
        "customer_gstin": "36AAACH7409R1ZZ",  # Telangana (36)
        "place_of_supply": "Telangana (36)",
        "cgst_amount": 900.0,
        "sgst_amount": 900.0,
        "igst_amount": None,
        "tax_total": 1800.0,
        "line_items": [
            {
                "description": "Consulting Services",
                "taxable_amount": 10000.0,
                "cgst_rate": 9.0,
                "sgst_rate": 9.0,
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["supplier_state_code"] == "36"
    assert result["place_of_supply_state_code"] == "36"
    assert result["supply_type"] == "INTRA_STATE"
    assert result["validation_status"] == "PASSED"
    assert result["calculated"]["cgst_amount"] == 900.0
    assert result["calculated"]["sgst_amount"] == 900.0
    assert result["calculated"]["igst_amount"] == 0.0
    assert len(result["errors"]) == 0


def test_2_different_supplier_pos_states():
    """2. Different supplier/POS states -> INTER_STATE -> IGST"""
    invoice_data = {
        "vendor_gstin": "07AABCU9603R1ZM",  # Delhi (07)
        "customer_gstin": "27AAACH7409R1ZZ",  # Maharashtra (27)
        "place_of_supply": "Maharashtra (27)",
        "cgst_amount": None,
        "sgst_amount": None,
        "igst_amount": 1800.0,
        "tax_total": 1800.0,
        "line_items": [
            {
                "description": "Server Hardware",
                "taxable_amount": 10000.0,
                "igst_rate": 18.0,
                "igst_amount": 1800.0,
            }
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["supplier_state_code"] == "07"
    assert result["place_of_supply_state_code"] == "27"
    assert result["supply_type"] == "INTER_STATE"
    assert result["validation_status"] == "PASSED"
    assert result["calculated"]["igst_amount"] == 1800.0
    assert result["calculated"]["cgst_amount"] == 0.0
    assert result["calculated"]["sgst_amount"] == 0.0


def test_3_pos_precedence_over_buyer_gstin():
    """3. Same GSTIN states but explicit different POS -> POS takes precedence"""
    invoice_data = {
        "vendor_gstin": "36AABCU9603R1ZM",  # Telangana (36)
        "customer_gstin": "36AAACH7409R1ZZ",  # Telangana (36)
        "place_of_supply": "Karnataka (29)",  # Explicit POS in Karnataka
        "igst_amount": 1800.0,
        "tax_total": 1800.0,
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["supplier_state_code"] == "36"
    assert result["buyer_state_code"] == "36"
    assert result["place_of_supply_state_code"] == "29"
    assert result["place_of_supply_source"] == "explicit_invoice"
    assert result["supply_type"] == "INTER_STATE"


def test_4_missing_pos_with_buyer_gstin_fallback():
    """4. Missing POS but valid buyer GSTIN -> fallback only for ordinary B2B case"""
    invoice_data = {
        "vendor_gstin": "24AABCU9603R1ZM",  # Gujarat (24)
        "customer_gstin": "27AAACH7409R1ZZ",  # Maharashtra (27)
        "place_of_supply": None,
        "igst_amount": 1800.0,
        "tax_total": 1800.0,
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["supplier_state_code"] == "24"
    assert result["buyer_state_code"] == "27"
    assert result["place_of_supply_state_code"] == "27"
    assert result["place_of_supply_source"] == "buyer_gstin_fallback"
    assert result["supply_type"] == "INTER_STATE"


def test_5_invalid_gstin_review_required():
    """5. Invalid GSTIN -> REVIEW_REQUIRED"""
    invoice_data = {
        "vendor_gstin": "INVALID123",
        "customer_gstin": "NOT_A_GSTIN",
        "place_of_supply": None,
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["supplier_state_code"] is None
    assert result["supply_type"] == "REVIEW_REQUIRED"
    assert result["validation_status"] == "REVIEW_REQUIRED"


def test_6_intra_state_unexpected_igst():
    """6. Intra-state + IGST -> GST_MISMATCH"""
    invoice_data = {
        "vendor_gstin": "36AABCU9603R1ZM",  # Telangana (36)
        "place_of_supply": "Telangana (36)",
        "cgst_amount": None,
        "sgst_amount": None,
        "igst_amount": 1800.0,  # Unexpected IGST for intra-state
        "tax_total": 1800.0,
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["supply_type"] == "INTRA_STATE"
    assert result["validation_status"] == "GST_MISMATCH"
    assert any("Unexpected IGST" in err for err in result["errors"])


def test_7_inter_state_unexpected_cgst_sgst():
    """7. Inter-state + CGST/SGST -> GST_MISMATCH"""
    invoice_data = {
        "vendor_gstin": "24AABCU9603R1ZM",  # Gujarat (24)
        "place_of_supply": "08-Rajasthan",  # Rajasthan (08)
        "cgst_amount": 248417.88,  # Unexpected CGST on inter-state
        "sgst_amount": 248417.88,  # Unexpected SGST on inter-state
        "tax_total": 496835.76,
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["supply_type"] == "INTER_STATE"
    assert result["validation_status"] == "GST_MISMATCH"
    assert any("Unexpected CGST/SGST" in err for err in result["errors"])


def test_8_multiple_gst_rates():
    """8. Support different GST rates on different invoice lines"""
    invoice_data = {
        "vendor_gstin": "36AABCU9603R1ZM",
        "place_of_supply": "36-Telangana",
        "line_items": [
            {
                "description": "Item 5% GST",
                "taxable_amount": 1000.0,
                "cgst_rate": 2.5,
                "sgst_rate": 2.5,
            },
            {
                "description": "Item 18% GST",
                "taxable_amount": 2000.0,
                "cgst_rate": 9.0,
                "sgst_rate": 9.0,
            },
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["calculated"]["cgst_amount"] == 205.0  # (1000*0.025 + 2000*0.09) = 25 + 180 = 205
    assert result["calculated"]["sgst_amount"] == 205.0
    assert result["calculated"]["gst_total"] == 410.0


def test_9_explicit_extracted_tax_values_preserved():
    """9. Explicit extracted tax values preserved exactly"""
    invoice_data = {
        "vendor_gstin": "24AABCU9603R1ZM",
        "place_of_supply": "08-Rajasthan",
        "additional_fields": {
            "CGST Amount": 248417.88,
            "S-GST": 248417.88,
            "Tax Amount": 496835.76,
        },
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["extracted"]["cgst_amount"] == 248417.88
    assert result["extracted"]["sgst_amount"] == 248417.88
    assert result["extracted"]["tax_total"] == 496835.76


def test_10_line_item_tax_aggregation():
    """10. Line-item tax aggregation when header is missing"""
    invoice_data = {
        "vendor_gstin": "27AABCU9603R1ZM",
        "place_of_supply": "27-Maharashtra",
        "line_items": [
            {"description": "A", "cgst_amount": 100.0, "sgst_amount": 100.0},
            {"description": "B", "cgst_amount": 200.0, "sgst_amount": 200.0},
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["extracted"]["cgst_amount"] == 300.0
    assert result["extracted"]["sgst_amount"] == 300.0


def test_11_no_double_counting():
    """11. No double counting between top-level and line items"""
    invoice_data = {
        "vendor_gstin": "27AABCU9603R1ZM",
        "place_of_supply": "27-Maharashtra",
        "cgst_amount": 300.0,
        "sgst_amount": 300.0,
        "line_items": [
            {"description": "A", "cgst_amount": 100.0, "sgst_amount": 100.0},
            {"description": "B", "cgst_amount": 200.0, "sgst_amount": 200.0},
        ],
    }
    result = gst_engine.evaluate_gst(invoice_data)
    # Header value 300.0 is used directly, not added to line sum
    assert result["extracted"]["cgst_amount"] == 300.0
    assert result["extracted"]["sgst_amount"] == 300.0


def test_12_itc_eligible_standard_business():
    """12. Normal business expense -> ITC ELIGIBLE (Section 16(1))"""
    invoice_data = {
        "line_items": [
            {
                "description": "AWS Cloud Hosting Infrastructure",
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
            }
        ]
    }
    accounting_output = {
        "accounting": [
            {
                "line_index": 1,
                "ai_account_name": "Cloud Infrastructure Expenses",
            }
        ]
    }
    itc_result = itc_engine.evaluate_itc(invoice_data, accounting_output)
    assert itc_result["status"] == "ELIGIBLE"
    assert itc_result["eligible_amount"] == 1800.0
    assert itc_result["ineligible_amount"] == 0.0
    assert "Sec 16(1)" in itc_result["rule_reference"]


def test_13_itc_blocked_food_and_catering():
    """13. Food & catering -> ITC INELIGIBLE (Section 17(5)(b)(i))"""
    invoice_data = {
        "line_items": [
            {
                "description": "Team lunch buffet and restaurant food catering",
                "cgst_amount": 250.0,
                "sgst_amount": 250.0,
            }
        ]
    }
    accounting_output = {
        "accounting": [
            {
                "line_index": 1,
                "ai_account_name": "Staff Welfare - Food & Refreshments",
            }
        ]
    }
    itc_result = itc_engine.evaluate_itc(invoice_data, accounting_output)
    assert itc_result["status"] == "INELIGIBLE"
    assert itc_result["eligible_amount"] == 0.0
    assert itc_result["ineligible_amount"] == 500.0
    assert "17(5)(b)(i)" in itc_result["rule_reference"]


def test_14_itc_review_required_insufficient_context():
    """14. Ambiguous context / missing description -> ITC REVIEW_REQUIRED"""
    invoice_data = {
        "line_items": [
            {
                "description": "Not provided",
                "cgst_amount": 100.0,
                "sgst_amount": 100.0,
            }
        ]
    }
    itc_result = itc_engine.evaluate_itc(invoice_data, None)
    assert itc_result["status"] == "REVIEW_REQUIRED"


def test_15_reverse_charge():
    """15. Reverse charge preservation and note in ITC result"""
    invoice_data = {
        "vendor_gstin": "36AABCU9603R1ZM",
        "place_of_supply": "36-Telangana",
        "reverse_charge": "Yes",
        "line_items": [
            {
                "description": "Legal & advocate advisory services",
                "cgst_amount": 900.0,
                "sgst_amount": 900.0,
            }
        ],
    }
    gst_res = gst_engine.evaluate_gst(invoice_data)
    itc_res = itc_engine.evaluate_itc(invoice_data, None)

    assert gst_res["is_reverse_charge"] is True
    assert itc_res["is_reverse_charge"] is True
    assert "Reverse Charge Supply" in itc_res["reason"]


def test_16_itc_tax_amount_aggregation_from_gst_components():
    """16. Total Tax Available derived strictly from CGST + SGST + IGST + Cess"""
    invoice_data = {
        "vendor_gstin": "33WUXFL2614T224",  # Tamil Nadu
        "customer_gstin": "29BMDNQ4069K220",  # Karnataka
        "cgst_amount": 636850.77,
        "sgst_amount": 636850.77,
        "igst_amount": None,
        "tax_total": 1273701.54,
        "subtotal": 7076119.66,
        "total_amount": 8349821.20,
    }
    itc_result = itc_engine.evaluate_itc(invoice_data, None)
    # Total tax must be exactly 12,73,701.54, NOT 127,370,154 or taxable amount
    assert itc_result["total_tax_amount"] == 1273701.54


def test_17_explicit_pos_in_additional_fields_takes_precedence():
    """17. Explicit POS in additional_fields or text takes precedence over buyer GSTIN fallback"""
    invoice_data = {
        "vendor_gstin": "33WUXFL2614T224",  # Tamil Nadu (33)
        "customer_gstin": "29BMDNQ4069K220",  # Karnataka (29)
        "additional_fields": {
            "Place of Supply": "Karnataka (29)",
        },
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["place_of_supply_state_code"] == "29"
    assert result["place_of_supply_state_name"] == "Karnataka"
    assert result["place_of_supply_source"] == "explicit_invoice"
    assert result["supply_type"] == "INTER_STATE"


def test_18_buyer_gstin_fallback_only_when_pos_absent():
    """18. Buyer GSTIN state used ONLY when explicit POS is genuinely absent"""
    invoice_data = {
        "vendor_gstin": "33WUXFL2614T224",  # Tamil Nadu (33)
        "customer_gstin": "29BMDNQ4069K220",  # Karnataka (29)
        "place_of_supply": None,
        "additional_fields": {},
    }
    result = gst_engine.evaluate_gst(invoice_data)
    assert result["place_of_supply_state_code"] == "29"
    assert result["place_of_supply_source"] == "buyer_gstin_fallback"


def test_19_itc_review_required_for_generic_retail_merchandise():
    """19. Generic retail / consumer goods without verified business use -> REVIEW_REQUIRED"""
    invoice_data = {
        "line_items": [
            {
                "description": "assorted retail merchandise for monthly store replenishment SKU DAI-7719",
                "cgst_amount": 1000.0,
                "sgst_amount": 1000.0,
            }
        ]
    }
    itc_result = itc_engine.evaluate_itc(invoice_data, None)
    assert itc_result["status"] == "REVIEW_REQUIRED"
    assert "Section 16(1)" in itc_result["reason"]


def test_20_itc_blocked_motor_vehicles():
    """20. Section 17(5)(a) blocked credit for passenger motor vehicle"""
    invoice_data = {
        "line_items": [
            {
                "description": "Passenger car motor vehicle sedan purchase",
                "cgst_amount": 50000.0,
                "sgst_amount": 50000.0,
            }
        ]
    }
    itc_result = itc_engine.evaluate_itc(invoice_data, None)
    assert itc_result["status"] == "INELIGIBLE"
    assert itc_result["ineligible_amount"] == 100000.0
    assert itc_result["eligible_amount"] == 0.0
    assert "17(5)(a)" in itc_result["rule_reference"]

